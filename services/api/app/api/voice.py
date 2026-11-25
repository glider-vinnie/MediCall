from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import AliasChoices, BaseModel, Field, ValidationError

from app.voice.session import VoiceSessionManager

router = APIRouter(tags=["voice"])


class VoiceSessionResponse(BaseModel):
    session_id: str
    offer_url: str
    events_url: str


class WebRTCOfferPayload(BaseModel):
    sdp: str
    type: Literal["offer"]
    pc_id: str | None = None
    restart_pc: bool | None = None
    request_data: Any | None = Field(
        default=None, validation_alias=AliasChoices("request_data", "requestData")
    )


class IceCandidatePayload(BaseModel):
    candidate: str
    sdp_mid: str
    sdp_mline_index: int


class WebRTCCandidatePatchPayload(BaseModel):
    pc_id: str
    candidates: list[IceCandidatePayload]


@router.get("/voice/config")
def voice_config(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "configured": settings.voice_is_configured,
        "mode": settings.effective_voice_mode,
        "missing_configuration": settings.voice_missing_configuration,
        "configuration_present": settings.voice_configuration_presence,
    }


@router.post("/voice/sessions", response_model=VoiceSessionResponse, status_code=201)
async def create_voice_session(request: Request) -> VoiceSessionResponse:
    settings = request.app.state.settings
    if not settings.voice_is_configured:
        raise HTTPException(status_code=503, detail={"code": "voice_not_configured", "message": "Live voice is unavailable. Configure provider credentials on the backend.", "missing_configuration": settings.voice_missing_configuration})
    session = await request.app.state.voice_sessions.create()
    await request.app.state.voice_events.publish(session.id, "call_connecting")
    base_url = str(request.base_url).rstrip("/")
    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    return VoiceSessionResponse(session_id=session.id, offer_url=f"{base_url}/api/voice/sessions/{session.id}/offer", events_url=f"{ws_base}/api/voice/events/{session.id}")


@router.post("/voice/sessions/{session_id}/offer")
async def offer_voice_connection(
    session_id: str, payload: dict[str, Any], request: Request
) -> dict[str, str]:
    manager: VoiceSessionManager = request.app.state.voice_sessions
    session = await manager.get(session_id)
    if session is None or session.state == "ended":
        logger.warning(
            "Voice offer rejected because its session is unavailable: fingerprint={}, active_sessions={}",
            manager._fingerprint(session_id),
            await manager.active_count(),
        )
        raise HTTPException(status_code=404, detail="Voice session not found or already ended.")
    try:
        offer = WebRTCOfferPayload.model_validate(payload)
    except ValidationError as error:
        session.state = "error"
        await request.app.state.voice_events.publish(session.id, "error", message="The browser sent an invalid WebRTC offer.")
        await manager.end(session.id)
        raise HTTPException(status_code=422, detail=error.errors()) from error
    if session.request_handler is None:
        from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequestHandler
        session.request_handler = SmallWebRTCRequestHandler(ice_servers=request.app.state.settings.ice_servers)
    from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest

    async def attach(connection) -> None:
        await request.app.state.voice_pipeline.attach(session, connection)

    try:
        answer = await session.request_handler.handle_web_request(
            SmallWebRTCRequest(**offer.model_dump(exclude_none=True)), attach
        )
    except HTTPException:
        session.state = "error"
        await request.app.state.voice_events.publish(session.id, "error", message="The voice connection request was rejected.")
        await manager.end(session.id)
        raise
    except Exception as error:
        session.state = "error"
        await request.app.state.voice_events.publish(session.id, "error", message="Unable to establish the voice connection.")
        await manager.end(session.id)
        raise HTTPException(status_code=502, detail="Unable to establish the voice connection.") from error
    if answer is None:
        session.state = "error"
        await request.app.state.voice_events.publish(session.id, "error", message="Voice transport did not return an answer.")
        await manager.end(session.id)
        raise HTTPException(status_code=502, detail="Voice transport did not return an answer.")
    return answer


@router.patch("/voice/sessions/{session_id}/offer", status_code=204)
async def add_voice_ice_candidates(
    session_id: str, payload: WebRTCCandidatePatchPayload, request: Request
) -> None:
    """Accept trickle ICE candidates emitted by the SmallWebRTC browser transport."""

    manager: VoiceSessionManager = request.app.state.voice_sessions
    session = await manager.get(session_id)
    if session is None or session.state == "ended":
        logger.warning(
            "Voice ICE patch rejected because its session is unavailable: fingerprint={}, active_sessions={}",
            manager._fingerprint(session_id),
            await manager.active_count(),
        )
        raise HTTPException(status_code=404, detail="Voice session not found or already ended.")
    if session.request_handler is None:
        raise HTTPException(status_code=409, detail="Create a WebRTC offer before sending ICE candidates.")

    from pipecat.transports.smallwebrtc.request_handler import IceCandidate, SmallWebRTCPatchRequest

    patch_request = SmallWebRTCPatchRequest(
        pc_id=payload.pc_id,
        candidates=[
            IceCandidate(
                candidate=candidate.candidate,
                sdp_mid=candidate.sdp_mid,
                sdp_mline_index=candidate.sdp_mline_index,
            )
            for candidate in payload.candidates
        ],
    )
    try:
        await session.request_handler.handle_patch_request(patch_request)
    except HTTPException:
        raise
    except Exception as error:
        session.state = "error"
        await request.app.state.voice_events.publish(session.id, "error", message="Unable to add a network candidate to the voice connection.")
        await manager.end(session.id)
        raise HTTPException(status_code=502, detail="Unable to add a network candidate to the voice connection.") from error


@router.delete("/voice/sessions/{session_id}", status_code=204)
async def end_voice_session(session_id: str, request: Request) -> None:
    session = await request.app.state.voice_sessions.end(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found.")
    await request.app.state.voice_events.publish(session_id, "call_ended")


@router.websocket("/voice/events/{session_id}")
async def voice_events(session_id: str, websocket: WebSocket) -> None:
    manager: VoiceSessionManager = websocket.app.state.voice_sessions
    if await manager.get(session_id) is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    hub = websocket.app.state.voice_events
    queue = hub.subscribe(session_id)
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(session_id, queue)
