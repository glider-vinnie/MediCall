import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiUrl, request } from "../lib/api";
import type { TranscriptItem, VoiceConfig, VoiceEvent, VoiceSession, VoiceStatus } from "../types/voice";

const websocketUrl = (url: string) => url.replace(/^http/, "ws");
const CONNECT_TIMEOUT_MS = 20_000;

const logVoice = (event: string, details: Record<string, unknown> = {}) => {
  // Keep browser diagnostics free of session identifiers, transcripts, and caller data.
  console.info("[MediCall voice]", { event, ...details });
};

const withTimeout = <T,>(promise: Promise<T>, timeoutMs: number, message: string) => new Promise<T>((resolve, reject) => {
  const timeout = window.setTimeout(() => reject(new Error(message)), timeoutMs);
  promise.then((value) => { window.clearTimeout(timeout); resolve(value); }, (reason) => { window.clearTimeout(timeout); reject(reason); });
});

const errorMessage = (reason: unknown, fallback: string) => {
  if (reason instanceof Error && reason.message) return reason.message;
  if (reason && typeof reason === "object") {
    const value = reason as { message?: unknown; data?: { message?: unknown; error?: unknown } };
    if (typeof value.message === "string" && value.message) return value.message;
    if (typeof value.data?.message === "string" && value.data.message) return value.data.message;
    if (typeof value.data?.error === "string" && value.data.error) return value.data.error;
  }
  return fallback;
};

const isAssistantOnlyError = (message: string) => /llm|gemini|assistant response|completion timeout|429|resource_exhausted|quota/i.test(message);

const assistantErrorMessage = (message: string) => {
  if (/429|resource_exhausted|quota/i.test(message)) {
    return "Gemini's request quota is exhausted. The call remains connected, but it cannot generate replies until the provider quota resets or the API project has available quota.";
  }
  if (/timeout/i.test(message)) return "The assistant response timed out. The call remains connected; please try again.";
  return message;
};

export function useVoiceCall(onAppointmentChange?: () => void) {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [connectionDetail, setConnectionDetail] = useState<string | null>(null);
  const client = useRef<PipecatClient | null>(null);
  const session = useRef<VoiceSession | null>(null);
  const events = useRef<WebSocket | null>(null);
  const remoteAudio = useRef<HTMLAudioElement | null>(null);
  const callAttempt = useRef(0);
  const startInFlight = useRef(false);

  const appendTranscript = useCallback((role: TranscriptItem["role"], text: string, final = true) => {
    const normalized = text.trim();
    if (!normalized) return;
    setTranscripts((current) => {
      const last = current.at(-1);
      if (role === "user") {
        // ElevenLabs updates an in-progress utterance. Keep one bubble until
        // its committed transcript arrives, then replace it with the final text.
        if (last?.role === "user" && !last.final) {
          return [...current.slice(0, -1), { ...last, text: normalized, final }];
        }
        if (last?.role === "user" && last.final && last.text === normalized) return current;
        return [...current, { id: crypto.randomUUID(), role, text: normalized, final }];
      }
      // The server event socket and RTVI data channel can both carry the same
      // real assistant text. Do not render an identical update twice.
      if (last?.role === role && last.text === normalized) return current;
      return [...current, { id: crypto.randomUUID(), role, text: normalized, final: true }];
    });
  }, []);

  const releaseRemoteAudio = useCallback(() => {
    const element = remoteAudio.current;
    if (!element) return;
    element.pause();
    element.srcObject = null;
    element.remove();
    remoteAudio.current = null;
    logVoice("remote_audio_released");
  }, []);

  const attachRemoteAudio = useCallback((track: MediaStreamTrack) => {
    if (track.kind !== "audio") return;
    releaseRemoteAudio();
    const element = document.createElement("audio");
    element.autoplay = true;
    element.setAttribute("playsinline", "");
    element.muted = false;
    element.volume = 1;
    element.srcObject = new MediaStream([track]);
    document.body.appendChild(element);
    remoteAudio.current = element;
    void element.play()
      .then(() => logVoice("remote_audio_playing"))
      .catch((reason) => {
        logVoice("remote_audio_playback_error");
        setError(errorMessage(reason, "Browser audio playback was blocked."));
        setConnectionDetail("Browser audio playback was blocked. Interact with the page and try again.");
      });
  }, [releaseRemoteAudio]);

  const releaseCall = useCallback(async () => {
    callAttempt.current += 1;
    events.current?.close();
    events.current = null;
    releaseRemoteAudio();
    const activeClient = client.current;
    client.current = null;
    try { await activeClient?.disconnect(); } catch { /* The server may have already disconnected. */ }
    logVoice("call_released");
    const active = session.current;
    session.current = null;
    if (active) await request<void>(`/api/voice/sessions/${active.session_id}`, { method: "DELETE" }).catch(() => undefined);
  }, [releaseRemoteAudio]);

  const end = useCallback(async () => {
    await releaseCall();
    setStatus("ended");
    setMuted(false);
  }, [releaseCall]);

  useEffect(() => {
    request<VoiceConfig>("/api/voice/config")
      .then((value) => { setConfig(value); setStatus(value.configured ? "idle" : "unavailable"); })
      .catch(() => { setConfig(null); setStatus("unavailable"); setError("Voice service is unavailable. Check that the backend is running."); });
    return () => { void end(); };
  }, [end]);

  const handleEvent = useCallback((event: VoiceEvent) => {
    logVoice("server_event", { type: event.type, role: event.role });
    if (event.type === "transcript" && event.role && event.text) {
      appendTranscript(event.role, event.text, event.final ?? true);
    }
    if (event.type === "tool") setToolStatus(event.status === "running" ? `${event.name} is running` : null);
    if (event.type === "booking_confirmed" && event.appointment) { setConfirmation(`Booked with ${event.appointment.doctor} on ${event.appointment.date} at ${event.appointment.start_time}.`); onAppointmentChange?.(); }
    if (event.type === "cancellation_confirmed" && event.appointment) { setConfirmation(`Cancelled the appointment with ${event.appointment.doctor}.`); onAppointmentChange?.(); }
    if (event.type === "assistant_error") {
      setError(assistantErrorMessage(event.message ?? "The assistant could not complete its response."));
      setConnectionDetail("Assistant request failed; the voice transport remains connected.");
    }
    if (event.type === "error") {
      const message = event.message ?? "The voice service reported an error.";
      setError(message);
      if (isAssistantOnlyError(message)) setConnectionDetail("Assistant request failed; the voice transport remains connected.");
      else { setConnectionDetail("The backend reported a voice-pipeline error."); setStatus("error"); }
    }
    if (event.type === "call_ended") setStatus("ended");
  }, [appendTranscript, onAppointmentChange]);

  const start = useCallback(async () => {
    if (!config?.configured) { setError("Live voice is not configured on this backend. This dashboard is in clearly labelled demo mode."); return; }
    if (startInFlight.current || session.current) return;
    startInFlight.current = true;
    const attempt = callAttempt.current + 1;
    callAttempt.current = attempt;
    let active: VoiceSession | null = null;
    setError(null); setConfirmation(null); setToolStatus(null); setTranscripts([]); setConnectionDetail("Requesting microphone access…"); setStatus("connecting");
    try {
      active = await request<VoiceSession>("/api/voice/sessions", { method: "POST" });
      logVoice("session_created");
      if (callAttempt.current !== attempt) {
        await request<void>(`/api/voice/sessions/${active.session_id}`, { method: "DELETE" }).catch(() => undefined);
        return;
      }
      session.current = active;
      const socket = new WebSocket(websocketUrl(active.events_url));
      socket.onopen = () => logVoice("event_socket_open");
      socket.onerror = () => logVoice("event_socket_error");
      socket.onclose = (closeEvent) => logVoice("event_socket_closed", { code: closeEvent.code, clean: closeEvent.wasClean });
      socket.onmessage = (message) => {
        try { handleEvent(JSON.parse(message.data) as VoiceEvent); } catch { logVoice("event_socket_invalid_message"); }
      };
      events.current = socket;
      const transport = new SmallWebRTCTransport({ webrtcRequestParams: { endpoint: active.offer_url } });
      const instance = new PipecatClient({
        transport, enableMic: true, enableCam: false,
        callbacks: {
          onConnected: () => logVoice("transport_connected"),
          onBotReady: () => { logVoice("bot_ready"); setConnectionDetail("Voice transport and assistant are ready."); if (client.current === instance) setStatus("connected"); },
          onUserTranscript: (data) => { logVoice("rtvi_user_transcript", { final: data.final }); appendTranscript("user", data.text, data.final); },
          onBotTranscript: (data) => { logVoice("rtvi_bot_transcript"); appendTranscript("assistant", data.text); },
          onDisconnected: () => {
            logVoice("transport_disconnected");
            if (client.current === instance) {
              client.current = null;
              events.current?.close();
              events.current = null;
              releaseRemoteAudio();
              const activeSession = session.current;
              session.current = null;
              if (activeSession) void request<void>(`/api/voice/sessions/${activeSession.session_id}`, { method: "DELETE" }).catch(() => undefined);
            }
            setStatus((current) => current === "error" ? current : "ended");
          },
          onTransportStateChanged: (transportState) => { logVoice("transport_state", { state: transportState }); setConnectionDetail(`Transport: ${transportState}.`); },
          onMediaStateChanged: (mediaState) => logVoice("media_state", { microphone: mediaState.mic.state }),
          onTrackStarted: (track, participant) => {
            const isLocal = participant?.local ?? false;
            logVoice("track_started", { kind: track.kind, local: isLocal, muted: track.muted, readyState: track.readyState });
            if (!isLocal) attachRemoteAudio(track);
          },
          onTrackStopped: (track) => {
            logVoice("track_stopped", { kind: track.kind, readyState: track.readyState });
            if (track.kind === "audio") releaseRemoteAudio();
          },
          onDeviceError: (deviceError) => { logVoice("microphone_error", { type: deviceError.type }); setError(errorMessage(deviceError, "Microphone permission was denied or no microphone is available.")); setConnectionDetail("Microphone setup failed."); setStatus("error"); },
          onError: (clientError) => {
            const message = errorMessage(clientError, "The browser could not connect to the voice service.");
            logVoice("client_error", { category: isAssistantOnlyError(message) ? "assistant" : "transport" });
            setError(isAssistantOnlyError(message) ? assistantErrorMessage(message) : message);
            if (isAssistantOnlyError(message)) {
              setConnectionDetail("Assistant request failed; the voice transport remains connected.");
            } else {
              setConnectionDetail(`WebRTC client error: ${message}`);
              setStatus("error");
            }
          },
        },
      });
      client.current = instance;
      await instance.initDevices();
      const micState = instance.mediaState.mic.state;
      const micTrack = transport.tracks().local.audio;
      logVoice("microphone_initialized", { state: micState, trackPresent: Boolean(micTrack), trackState: micTrack?.readyState });
      if (micState !== "granted" || !micTrack || micTrack.readyState !== "live") throw new Error("A live microphone track was not available after permission was granted.");
      setConnectionDetail("Microphone ready. Negotiating secure audio…");
      await withTimeout(instance.connect(), CONNECT_TIMEOUT_MS, "The voice transport did not become ready within 20 seconds. Check the browser console diagnostics and backend logs.");
      if (callAttempt.current === attempt) { setConnectionDetail("Voice transport and assistant are ready."); setStatus("connected"); }
    } catch (reason) {
      if (session.current?.session_id === active?.session_id) await releaseCall();
      else if (active) await request<void>(`/api/voice/sessions/${active.session_id}`, { method: "DELETE" }).catch(() => undefined);
      setError(errorMessage(reason, "Unable to start a voice call."));
      setConnectionDetail("Voice connection failed. See the browser console for safe diagnostics.");
      setStatus("error");
    } finally {
      startInFlight.current = false;
    }
  }, [appendTranscript, attachRemoteAudio, config?.configured, handleEvent, releaseCall, releaseRemoteAudio]);

  const toggleMute = useCallback(() => {
    const next = !muted;
    client.current?.enableMic(!next);
    setMuted(next);
  }, [muted]);

  return { config, status, error, muted, transcripts, toolStatus, confirmation, connectionDetail, start, end, toggleMute, apiUrl };
}
