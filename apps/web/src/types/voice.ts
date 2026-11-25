export type VoiceStatus = "unavailable" | "idle" | "connecting" | "connected" | "ended" | "error";

export interface VoiceConfig {
  configured: boolean;
  mode: "live" | "demo";
  missing_configuration: string[];
}

export interface VoiceSession {
  session_id: string;
  offer_url: string;
  events_url: string;
}

export interface TranscriptItem {
  id: string;
  role: "user" | "assistant";
  text: string;
  final?: boolean;
}

export interface VoiceEvent {
  type: string;
  role?: "user" | "assistant";
  text?: string;
  final?: boolean;
  message?: string;
  name?: string;
  status?: "running" | "completed" | "error";
  appointment?: { appointment_id: number; doctor: string; date: string; start_time: string; status: string };
}
