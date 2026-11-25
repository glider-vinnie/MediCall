from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import ErrorFrame, InputAudioRawFrame, InterimTranscriptionFrame, LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame, TTSAudioRawFrame, TranscriptionFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.elevenlabs.stt import CommitStrategy, ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_start import (
    TranscriptionUserTurnStartStrategy,
    VADUserTurnStartStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from app.core.config import Settings
from app.db.database import Database
from app.voice.events import VoiceEventHub
from app.voice.gemini import ResilientGoogleLLMService
from app.voice.prompt import SYSTEM_PROMPT
from app.voice.session import VoiceSession
from app.voice.tools import VoiceAppointmentTools


def _safe_provider_error(message: str) -> str:
    """Turn provider errors into useful UI text without relaying raw payloads."""

    normalized = message.lower()
    if "429" in normalized or "resource_exhausted" in normalized or "quota" in normalized:
        return (
            "Gemini's request quota is currently exhausted. The call remains connected, "
            "but replies will resume only after the provider quota resets or the API project has available quota."
        )
    if "timeout" in normalized:
        return "The assistant response timed out. The call remains connected; please try again."
    return "The assistant provider could not complete its response. The call remains connected; please try again."


class VoiceEventProcessor(FrameProcessor):
    """Publishes real transcript events and safe pipeline-stage diagnostics."""

    def __init__(self, session: VoiceSession, events: VoiceEventHub, stage: str) -> None:
        super().__init__()
        self._session = session
        self._events = events
        self._stage = stage
        self._audio_frames = 0
        self._first_llm_token_seen = False

    def _log(self, event: str, **details: Any) -> None:
        from loguru import logger

        fingerprint = hashlib.sha256(self._session.id.encode("utf-8")).hexdigest()[:12]
        logger.info("Voice pipeline {}: session={}, stage={}, {}", event, fingerprint, self._stage, details)

    async def process_frame(self, frame, direction: FrameDirection):
        # Preserve Pipecat's lifecycle/interruption bookkeeping before this
        # observer emits diagnostics or forwards the frame.
        await super().process_frame(frame, direction)
        if self._stage == "input" and isinstance(frame, InputAudioRawFrame):
            self._audio_frames += 1
            if self._audio_frames in {1, 50}:
                self._log("input_audio", frame_count=self._audio_frames, sample_rate=frame.sample_rate)
        elif self._stage == "stt" and isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
            # ElevenLabs marks VAD-committed frames as non-finalized even though
            # they are complete utterances. Only committed (not interim) frames
            # are eligible to carry a confirmation into the session state.
            finalized = isinstance(frame, TranscriptionFrame)
            if finalized:
                self._session.note_user_transcript(frame.text)
            self._log("transcript_received", final=finalized)
            await self._events.publish(
                self._session.id, "transcript", role="user", text=frame.text, final=finalized
            )
        elif self._stage == "assistant" and isinstance(frame, LLMTextFrame):
            if not self._first_llm_token_seen:
                self._first_llm_token_seen = True
                self._log("gemini_first_token")
            await self._events.publish(self._session.id, "transcript", role="assistant", text=frame.text)
        elif self._stage == "assistant" and isinstance(frame, LLMFullResponseStartFrame):
            self._first_llm_token_seen = False
            self._log("gemini_response_started")
        elif self._stage == "assistant" and isinstance(frame, LLMFullResponseEndFrame):
            self._log("gemini_response_completed")
        elif self._stage == "output" and isinstance(frame, TTSAudioRawFrame):
            self._audio_frames += 1
            if self._audio_frames in {1, 50}:
                self._log("tts_audio", frame_count=self._audio_frames, sample_rate=frame.sample_rate)
        elif self._stage == "input" and isinstance(frame, ErrorFrame):
            # Provider errors travel upstream in Pipecat, so observe them at
            # the input boundary rather than waiting at the output transport.
            self._log("provider_error")
            await self._events.publish(
                self._session.id, "assistant_error", message=_safe_provider_error(frame.error)
            )
        await self.push_frame(frame, direction)


class VoicePipelineFactory:
    def __init__(self, settings: Settings, database: Database, events: VoiceEventHub) -> None:
        self._settings = settings
        self._database = database
        self._events = events

    async def attach(self, session: VoiceSession, connection: SmallWebRTCConnection) -> None:
        tools = VoiceAppointmentTools(session, self._database.session_factory, self._events)
        transport = SmallWebRTCTransport(
            webrtc_connection=connection,
            params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        )
        stt = ElevenLabsRealtimeSTTService(
            api_key=self._settings.elevenlabs_api_key or "",
            model=self._settings.elevenlabs_stt_model,
            commit_strategy=CommitStrategy.VAD,
            params=ElevenLabsRealtimeSTTService.InputParams(language_code=self._settings.voice_language),
        )
        llm = ResilientGoogleLLMService(
            api_key=self._settings.gemini_api_key or "",
            model=self._settings.gemini_model,
            system_instruction=SYSTEM_PROMPT,
            # Gemini 3.5 Flash can occasionally take longer than the SDK's
            # 20-second first-token limit. Retry one stalled request and keep
            # the media transport alive while this bounded retry is attempted.
            stream_idle_timeout_secs=45.0,
            retry_timeout_secs=10.0,
            retry_on_timeout=True,
        )
        tts = ElevenLabsTTSService(
            api_key=self._settings.elevenlabs_api_key or "",
            voice_id=self._settings.elevenlabs_voice_id,
            model=self._settings.elevenlabs_tts_model,
        )
        context = LLMContext(tools=tools.pipecat_tools())
        # ElevenLabs emits VAD-committed transcripts without marking them
        # final. Pair local VAD with the deterministic speech-timeout strategy
        # so that a committed transcript is added to the context before Gemini
        # runs. Smart Turn produced empty recovery turns for this combination.
        aggregators = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
                user_turn_strategies=UserTurnStrategies(
                    # Realtime STT commits arrive after VAD detects speech.
                    # Interrupting the pipeline at turn start was cancelling
                    # that delayed committed frame before the LLM saw it.
                    start=[
                        VADUserTurnStartStrategy(enable_interruptions=False),
                        TranscriptionUserTurnStartStrategy(enable_interruptions=False),
                    ],
                    stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.35)]
                ),
                # Never ask Gemini to answer an unheard/empty turn.
                empty_user_turn=None,
            ),
        )
        input_observer = VoiceEventProcessor(session, self._events, "input")
        stt_observer = VoiceEventProcessor(session, self._events, "stt")
        assistant_observer = VoiceEventProcessor(session, self._events, "assistant")
        output_observer = VoiceEventProcessor(session, self._events, "output")

        @aggregators.user().event_handler("on_user_turn_message_added")
        async def on_user_turn_message_added(_, __) -> None:
            input_observer._log("gemini_request_started", model=self._settings.gemini_model)

        @llm.event_handler("on_completion_timeout")
        async def on_completion_timeout(_) -> None:
            input_observer._log("gemini_timeout")
            await self._events.publish(
                session.id,
                "assistant_error",
                message="The assistant response timed out. Your call is still connected; please try again.",
            )
        pipeline = Pipeline([
            transport.input(), input_observer, stt, stt_observer, aggregators.user(), llm, assistant_observer, tts, output_observer, transport.output(), aggregators.assistant()
        ])
        task = PipelineTask(pipeline, params=PipelineParams())

        @transport.event_handler("on_client_connected")
        async def on_client_connected(_, __):
            session.state = "connected"
            input_observer._log("webrtc_client_connected")
            await self._events.publish(session.id, "call_connected")

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(_, __):
            session.state = "ended"
            input_observer._log("webrtc_client_disconnected")
            await self._events.publish(session.id, "call_ended")

        async def run() -> None:
            try:
                await PipelineRunner(handle_sigint=False).run(task)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                session.state = "error"
                input_observer._log("pipeline_terminated", exception_type=type(error).__name__)
                await self._events.publish(session.id, "error", message="The voice service ended unexpectedly.")

        session.runner_task = asyncio.create_task(run())
