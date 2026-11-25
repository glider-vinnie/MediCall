from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.domain.phone import AFFIRMATIVE_RESPONSES, CallSessionPhoneVerification


@dataclass
class VoiceSession:
    id: str
    phone: CallSessionPhoneVerification = field(default_factory=CallSessionPhoneVerification)
    state: str = "connecting"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pending_cancellation_id: int | None = None
    cancellation_confirmed_for: int | None = None
    pending_booking_slot_id: int | None = None
    booking_confirmed_for: int | None = None
    request_handler: Any | None = None
    runner_task: asyncio.Task[None] | None = None

    def note_user_transcript(self, text: str) -> None:
        """Record only security-relevant intent, never the transcript itself."""
        if self.pending_cancellation_id is not None and text.strip().lower() in AFFIRMATIVE_RESPONSES:
            self.cancellation_confirmed_for = self.pending_cancellation_id
        if self.pending_booking_slot_id is not None and text.strip().lower() in AFFIRMATIVE_RESPONSES:
            self.booking_confirmed_for = self.pending_booking_slot_id

    def request_booking_confirmation(self, slot_id: int) -> bool:
        if self.pending_booking_slot_id != slot_id:
            self.pending_booking_slot_id = slot_id
            self.booking_confirmed_for = None
            return False
        return self.booking_confirmed_for == slot_id

    def complete_booking(self) -> None:
        self.pending_booking_slot_id = None
        self.booking_confirmed_for = None

    def request_cancellation_confirmation(self, appointment_id: int) -> bool:
        if self.pending_cancellation_id != appointment_id:
            self.pending_cancellation_id = appointment_id
            self.cancellation_confirmed_for = None
            return False
        return self.cancellation_confirmed_for == appointment_id

    def complete_cancellation(self) -> None:
        self.pending_cancellation_id = None
        self.cancellation_confirmed_for = None


class VoiceSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> VoiceSession:
        session = VoiceSession(id=secrets.token_urlsafe(24))
        async with self._lock:
            self._sessions[session.id] = session
            active_sessions = len(self._sessions)
        logger.info(
            "Voice session created: fingerprint={}, active_sessions={}",
            self._fingerprint(session.id),
            active_sessions,
        )
        return session

    async def get(self, session_id: str) -> VoiceSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def end(self, session_id: str) -> VoiceSession | None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            active_sessions = len(self._sessions)
        if session is None:
            logger.warning(
                "Voice session end requested for unknown session: fingerprint={}, active_sessions={}",
                self._fingerprint(session_id),
                active_sessions,
            )
            return None
        session.state = "ended"
        if session.runner_task and not session.runner_task.done():
            session.runner_task.cancel()
        if session.request_handler is not None:
            await session.request_handler.close()
        logger.info(
            "Voice session ended: fingerprint={}, active_sessions={}",
            self._fingerprint(session_id),
            active_sessions,
        )
        return session

    async def active_count(self) -> int:
        """Return only a count for safe lifecycle diagnostics."""
        async with self._lock:
            return len(self._sessions)

    @staticmethod
    def _fingerprint(session_id: str) -> str:
        """Use a non-reversible identifier in logs rather than a session capability."""
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]

    async def cleanup_all(self) -> None:
        for session_id in tuple(self._sessions):
            await self.end(session_id)
