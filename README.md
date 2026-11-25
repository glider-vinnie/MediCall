# MediCall AI

MediCall AI is a voice-based doctor appointment assistant. Milestone 4 adds an opt-in, browser-to-backend live voice path with Pipecat, SmallWebRTC, ElevenLabs Realtime STT/TTS, and Gemini tool calling. The appointment domain remains the source of truth for verification, ownership, transactions, and double-booking protection.

## Repository layout

```text
apps/web/                 React + TypeScript + Vite + Tailwind dashboard
services/api/             FastAPI backend
  app/api/                HTTP route modules
  app/core/               Configuration and application wiring
  app/db/                 SQLite models, engine, and idempotent seed data
  app/domain/             Appointment business logic and caller verification
  app/voice/              Pipecat pipeline, server sessions, events, and tools
docs/                     API and pipeline notes
data/                     Ignored local SQLite database location
```

## Run locally

Prerequisites: Node.js 20+ and Python 3.11+.

### Backend

```powershell
cd services/api
uv sync --extra dev
copy .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

The backend runs at `http://127.0.0.1:8000`. It creates and seeds `data/medicall.db` at startup (relative to `services/api`) with six doctors and seven days of future slots. Restarting does not duplicate doctors or slots. To reset demo data, stop the API and delete `data/medicall.db`, then restart it.

`uv` can be installed from [Astral's uv documentation](https://docs.astral.sh/uv/). Developers who prefer `venv` may install the project with `python -m pip install -e ".[dev]"` instead.

### Voice provider setup

Live calls are disabled by default. Add these **server-only** values to `services/api/.env`; never add them to `apps/web/.env` or commit them:

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_STT_MODEL=scribe_v2_realtime
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
VOICE_LANGUAGE=en
# Optional for production NAT traversal; comma-separated STUN/TURN URLs.
VOICE_ICE_SERVERS=
```

When any required provider setting is missing, `GET /api/voice/config` reports `mode: demo` and the dashboard labels its receptionist as **Demo mode · not connected**. It does not generate fake audio, transcripts, call status, bookings, or cancellations.

The default Gemini model is `gemini-3.5-flash`. The former `gemini-2.5-flash` setting is no longer available to newly provisioned Google AI accounts. Set `GEMINI_MODEL` only to a model exposed by your own Google AI account. MediCall uses `ELEVENLABS_VOICE_ID` as a server-only value; select a voice your ElevenLabs account can access (the project was validated with the premade George voice, `JBFqnCBsd6RMkjVDRZzb`).

### Frontend

In a second terminal:

```powershell
cd apps/web
copy .env.example .env
pnpm install
pnpm run dev
```

Vite prints the local dashboard URL, normally `http://127.0.0.1:5173`.

## Backend API

- `GET /api/health` — service health and the effective voice mode (`live` only when all required server-side provider settings are present).
- `GET /api/doctors?specialty=` — doctor catalogue.
- `GET /api/slots?doctor_id=&date=YYYY-MM-DD&specialty=` — future available slots only.
- `GET /api/appointments` — dashboard appointment view; patient phone numbers are always masked.
- `GET /api/voice/config` — whether server-side live voice configuration is ready; exposes no credentials.
- `POST /api/voice/sessions` — creates a credentials-gated, server-owned live call session.
- `POST /api/voice/sessions/{id}/offer` — SmallWebRTC signaling for that session.
- `PATCH /api/voice/sessions/{id}/offer` — SmallWebRTC trickle-ICE candidates for that session.
- `DELETE /api/voice/sessions/{id}` — ends a voice session and frees its transport.
- `WS /api/voice/events/{id}` — real lifecycle, transcript, tool, booking/cancellation, and error events.

There are intentionally no public booking or cancellation REST routes. Only the live pipeline invokes the internal appointment services.

## Live voice flow

1. The dashboard requests a server voice session only after the caller presses **Start call**. The browser then requests microphone permission.
2. The Pipecat browser client connects to the FastAPI SmallWebRTC signaling route. Provider keys never enter the browser.
3. Audio flows through ElevenLabs Realtime STT → Gemini → ElevenLabs TTS. Real events are displayed in the dashboard; the UI does not fabricate them.
4. Gemini can only call the session-bound tools: availability, capture/confirm phone, appointments, booking, and cancellation.
5. Phone numbers are normalized and read back digit by digit by the existing `CallSessionPhoneVerification` object. Booking and cancellation remain blocked until explicit confirmation. A changed phone resets verification.
6. Cancellation additionally requires server-recorded affirmative consent for the selected appointment. Database transactions and constraints still perform the final booking/cancellation checks.

To start a call, set the provider values above, restart the backend, open the dashboard, select **AI receptionist**, then press **Start call**. A local SmallWebRTC setup works for a development browser on the same machine. Configure `VOICE_ICE_SERVERS` with production-grade STUN/TURN infrastructure before deploying across restrictive NATs.

### Provider verification and known limitations

The backend’s `/api/voice/config` endpoint checks only that server-side values are present; it never returns them. Before a production rollout, validate the selected ElevenLabs voice and both provider WebSocket handshakes with the account that will run the service. A live browser call still requires a person to grant microphone permission, speak, and confirm audible playback—automated backend checks cannot verify the physical microphone or speakers.

## Database and tests

SQLite configuration is controlled by `DATABASE_URL` in [`services/api/.env.example`](services/api/.env.example). The schema contains doctors, slots, and appointments with foreign keys, indexes, slot uniqueness, status checks, and an appointment-per-slot constraint. Booking uses a transaction plus a conditional slot-status update; the database uniqueness rule remains the final double-booking guard.

Run backend tests:

```powershell
cd services/api
uv run pytest
```

## Safety rules

The backend now enforces these rules independently from any future LLM or Pipecat prompt:

- A caller is identified only by the phone number spoken in the active call.
- The agent reads that phone number back and receives explicit confirmation before booking or cancellation.
- `get_my_appointments` uses only the confirmed phone held in the active call session.
- Cancellation requires selecting the intended appointment plus confirmed caller phone.
- SQLite transactions and constraints prevent one slot from being double-booked.
- If external AI services are unavailable, the interface shows a clearly labelled **Demo mode · not connected** state; it is never represented as a live AI call.
