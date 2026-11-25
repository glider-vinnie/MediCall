import type { Appointment, Doctor, Health, Slot } from "../types/api";

export const apiUrl = (import.meta.env.VITE_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(`The service returned ${response.status}.`, response.status);
  }
  return response.json() as Promise<T>;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { ...options, headers: { "Content-Type": "application/json", ...options.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | { message?: string } } | null;
    const message = typeof body?.detail === "string" ? body.detail : body?.detail?.message ?? `The service returned ${response.status}.`;
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => get<Health>("/api/health", signal),
  doctors: (signal?: AbortSignal) => get<Doctor[]>("/api/doctors", signal),
  slots: (signal?: AbortSignal) => get<Slot[]>("/api/slots", signal),
  appointments: (signal?: AbortSignal) => get<Appointment[]>("/api/appointments", signal),
};
