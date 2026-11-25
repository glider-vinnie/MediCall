from __future__ import annotations

import hashlib
import time
from datetime import date as Date
from typing import Any

from loguru import logger
from sqlalchemy.orm import sessionmaker
from pipecat.services.llm_service import FunctionCallParams

from app.domain.appointments import (
    book_appointment as book_appointment_service,
    cancel_appointment as cancel_appointment_service,
    check_doctor_availability,
    get_my_appointments as get_my_appointments_service,
)
from app.domain.errors import DomainError
from app.voice.events import VoiceEventHub
from app.voice.session import VoiceSession


def _slot_payload(slot: Any) -> dict[str, Any]:
    return {
        "slot_id": slot.id,
        "doctor": slot.doctor.name,
        "specialty": slot.doctor.specialty,
        "date": slot.appointment_date.isoformat(),
        "start_time": slot.start_time.isoformat(timespec="minutes"),
        "end_time": slot.end_time.isoformat(timespec="minutes"),
    }


def _appointment_payload(appointment: Any) -> dict[str, Any]:
    return {
        "appointment_id": appointment.id,
        "doctor": appointment.doctor.name,
        "specialty": appointment.doctor.specialty,
        "date": appointment.appointment_date.isoformat(),
        "start_time": appointment.start_time.isoformat(timespec="minutes"),
        "status": appointment.status,
    }


class VoiceAppointmentTools:
    """A tool facade bound to one server-side call session.

    The LLM receives no way to submit an alternate verified identity: each
    mutation receives the session's own CallSessionPhoneVerification object.
    """

    def __init__(self, session: VoiceSession, sessions: sessionmaker, events: VoiceEventHub) -> None:
        self._call = session
        self._sessions = sessions
        self._events = events

    def _log(self, event: str, name: str, **details: Any) -> None:
        fingerprint = hashlib.sha256(self._call.id.encode("utf-8")).hexdigest()[:12]
        logger.info("Voice tool {}: session={}, tool={}, {}", event, fingerprint, name, details)

    async def _run(self, name: str, operation) -> dict[str, Any]:
        started_at = time.monotonic()
        self._log("started", name)
        await self._events.publish(self._call.id, "tool", name=name, status="running")
        try:
            result = operation()
        except DomainError as error:
            payload = {"ok": False, "code": error.code, "message": error.message}
            self._log("completed", name, ok=False, duration_ms=round((time.monotonic() - started_at) * 1000))
            await self._events.publish(self._call.id, "tool", name=name, status="error", message=error.message)
            return payload
        except (TypeError, ValueError) as error:
            payload = {"ok": False, "code": "invalid_input", "message": str(error)}
            self._log("completed", name, ok=False, duration_ms=round((time.monotonic() - started_at) * 1000))
            await self._events.publish(self._call.id, "tool", name=name, status="error", message=str(error))
            return payload
        self._log("completed", name, ok=True, duration_ms=round((time.monotonic() - started_at) * 1000))
        await self._events.publish(self._call.id, "tool", name=name, status="completed")
        return result

    async def check_doctor_availability(
        self, doctor_name: str | None = None, specialty: str | None = None, date: str | None = None
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            appointment_date = Date.fromisoformat(date) if date else None
            with self._sessions() as db:
                slots = check_doctor_availability(db, appointment_date=appointment_date, specialty=specialty)
                if doctor_name:
                    slots = [slot for slot in slots if doctor_name.lower() in slot.doctor.name.lower()]
                return {"ok": True, "slots": [_slot_payload(slot) for slot in slots[:12]]}

        return await self._run("check_doctor_availability", operation)

    async def capture_caller_phone(self, spoken_phone: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            changed = self._call.phone.phone_number != None
            normalized = self._call.phone.capture_spoken_phone(spoken_phone)
            self._call.pending_cancellation_id = None
            self._call.cancellation_confirmed_for = None
            self._call.pending_booking_slot_id = None
            self._call.booking_confirmed_for = None
            return {
                "ok": True,
                "requires_confirmation": True,
                "phone_readback": self._call.phone.digit_by_digit_readback(),
                "identity_reset": changed and not self._call.phone.is_verified,
                "message": "Read the digits back one at a time and ask the caller to confirm them.",
            }

        return await self._run("capture_caller_phone", operation)

    async def confirm_caller_phone(self, confirmed: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            verified = self._call.phone.confirm_phone(confirmed)
            return {
                "ok": verified,
                "verified": verified,
                "message": "Phone number verified." if verified else "Phone number was not confirmed. Ask for it again.",
            }

        return await self._run("confirm_caller_phone", operation)

    async def get_my_appointments(self) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            with self._sessions() as db:
                appointments = get_my_appointments_service(db, self._call.phone)
                return {"ok": True, "appointments": [_appointment_payload(item) for item in appointments]}

        return await self._run("get_my_appointments", operation)

    async def book_appointment(self, slot_id: int) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            self._call.phone.require_verified_phone()
            if not self._call.request_booking_confirmation(slot_id):
                return {
                    "ok": False,
                    "code": "booking_confirmation_required",
                    "message": "Ask the caller to explicitly confirm this slot, then call this tool again.",
                }
            with self._sessions() as db:
                appointment = book_appointment_service(db, self._call.phone, slot_id)
                db.refresh(appointment)
                appointment.doctor
                payload = {"ok": True, "appointment": _appointment_payload(appointment)}
            self._call.complete_booking()
            return payload

        result = await self._run("book_appointment", operation)
        if result.get("ok"):
            await self._events.publish(self._call.id, "booking_confirmed", appointment=result["appointment"])
        return result

    async def cancel_appointment(self, appointment_id: int) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            # This also enforces verified caller context before we create a pending action.
            self._call.phone.require_verified_phone()
            with self._sessions() as db:
                owned = {item.id: item for item in get_my_appointments_service(db, self._call.phone)}
                appointment = owned.get(appointment_id)
                if appointment is None:
                    return {"ok": False, "code": "not_found", "message": "No matching appointment was found for the verified phone number."}
                if appointment.status != "booked":
                    return {"ok": False, "code": "conflict", "message": "That appointment has already been cancelled."}
            if not self._call.request_cancellation_confirmation(appointment_id):
                return {
                    "ok": False,
                    "code": "cancellation_confirmation_required",
                    "message": "Ask the caller to explicitly confirm cancellation of this appointment, then call this tool again.",
                }
            with self._sessions() as db:
                appointment = cancel_appointment_service(db, self._call.phone, appointment_id)
                db.refresh(appointment)
                appointment.doctor
                payload = {"ok": True, "appointment": _appointment_payload(appointment)}
            self._call.complete_cancellation()
            return payload

        result = await self._run("cancel_appointment", operation)
        if result.get("ok"):
            await self._events.publish(self._call.id, "cancellation_confirmed", appointment=result["appointment"])
        return result

    def pipecat_tools(self) -> list[Any]:
        async def check_doctor_availability(params: FunctionCallParams, doctor_name: str | None = None, specialty: str | None = None, date: str | None = None):
            await params.result_callback(await self.check_doctor_availability(doctor_name, specialty, date))

        async def capture_caller_phone(params: FunctionCallParams, spoken_phone: str):
            await params.result_callback(await self.capture_caller_phone(spoken_phone))

        async def confirm_caller_phone(params: FunctionCallParams, confirmed: str):
            await params.result_callback(await self.confirm_caller_phone(confirmed))

        async def get_my_appointments(params: FunctionCallParams):
            await params.result_callback(await self.get_my_appointments())

        async def book_appointment(params: FunctionCallParams, slot_id: int):
            await params.result_callback(await self.book_appointment(slot_id))

        async def cancel_appointment(params: FunctionCallParams, appointment_id: int):
            await params.result_callback(await self.cancel_appointment(appointment_id))

        return [
            check_doctor_availability,
            capture_caller_phone,
            confirm_caller_phone,
            get_my_appointments,
            book_appointment,
            cancel_appointment,
        ]
