import asyncio

from app.db.database import Database, create_schema
from app.db.seed import seed_database
from app.domain.appointments import check_doctor_availability
from app.voice.events import VoiceEventHub
from app.voice.session import VoiceSession, VoiceSessionManager
from app.voice.tools import VoiceAppointmentTools


class PatchRecordingHandler:
    def __init__(self) -> None:
        self.patch_request = None
        self.closed = False

    async def handle_patch_request(self, patch_request) -> None:
        self.patch_request = patch_request

    async def close(self) -> None:
        self.closed = True


class FailingOfferHandler(PatchRecordingHandler):
    async def handle_web_request(self, *_args) -> None:
        raise RuntimeError("signaling failed")


class SuccessfulOfferHandler(PatchRecordingHandler):
    async def handle_web_request(self, request, _attach) -> dict[str, str]:
        self.offer_request = request
        return {"sdp": "answer", "type": "answer", "pc_id": "server-peer"}


def make_tools(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'voice.db'}")
    create_schema(database)
    with database.session_factory() as session:
        seed_database(session)
    call = VoiceSession(id="voice-test")
    return database, call, VoiceAppointmentTools(call, database.session_factory, VoiceEventHub())


def test_voice_tools_do_not_book_until_phone_is_explicitly_confirmed(tmp_path) -> None:
    database, call, tools = make_tools(tmp_path)
    with database.session_factory() as db:
        slot_id = check_doctor_availability(db)[0].id

    async def run():
        captured = await tools.capture_caller_phone("9876543210")
        blocked = await tools.book_appointment(slot_id)
        declined = await tools.confirm_caller_phone("no")
        still_blocked = await tools.book_appointment(slot_id)
        confirmed = await tools.confirm_caller_phone("yes")
        needs_booking_consent = await tools.book_appointment(slot_id)
        call.note_user_transcript("yes")
        booked = await tools.book_appointment(slot_id)
        return captured, blocked, declined, still_blocked, confirmed, needs_booking_consent, booked

    captured, blocked, declined, still_blocked, confirmed, needs_booking_consent, booked = asyncio.run(run())
    assert captured["requires_confirmation"] is True
    assert blocked["code"] == "phone_verification_required"
    assert declined["verified"] is False
    assert still_blocked["code"] == "phone_verification_required"
    assert confirmed["verified"] is True
    assert needs_booking_consent["code"] == "booking_confirmation_required"
    assert booked["ok"] is True


def test_voice_phone_change_resets_identity_and_cancellation_needs_consent(tmp_path) -> None:
    database, call, tools = make_tools(tmp_path)
    with database.session_factory() as db:
        slot_id = check_doctor_availability(db)[0].id

    async def run():
        await tools.capture_caller_phone("9876543210")
        await tools.confirm_caller_phone("yes")
        await tools.book_appointment(slot_id)
        call.note_user_transcript("yes")
        booked = await tools.book_appointment(slot_id)
        initial_cancel = await tools.cancel_appointment(booked["appointment"]["appointment_id"])
        call.note_user_transcript("yes")
        completed_cancel = await tools.cancel_appointment(booked["appointment"]["appointment_id"])
        await tools.capture_caller_phone("9123456789")
        mine = await tools.get_my_appointments()
        return initial_cancel, completed_cancel, mine

    initial_cancel, completed_cancel, mine = asyncio.run(run())
    assert initial_cancel["code"] == "cancellation_confirmation_required"
    assert completed_cancel["ok"] is True
    assert mine["code"] == "phone_verification_required"


def test_voice_session_cleanup_removes_server_owned_session() -> None:
    async def run():
        manager = VoiceSessionManager()
        call = await manager.create()
        assert await manager.get(call.id) is call
        ended = await manager.end(call.id)
        return ended, await manager.get(call.id)

    ended, missing = asyncio.run(run())
    assert ended is not None
    assert ended.state == "ended"
    assert missing is None


def test_create_session_followed_by_offer_uses_the_same_server_owned_session(app, client) -> None:
    response = client.post("/api/voice/sessions")

    assert response.status_code == 201
    payload = response.json()
    assert payload["offer_url"].endswith(f"/api/voice/sessions/{payload['session_id']}/offer")
    assert payload["events_url"].endswith(f"/api/voice/events/{payload['session_id']}")
    session = asyncio.run(app.state.voice_sessions.get(payload["session_id"]))
    assert session is not None
    handler = SuccessfulOfferHandler()
    session.request_handler = handler

    offer = client.post(payload["offer_url"], json={"sdp": "offer", "type": "offer"})

    assert offer.status_code == 200
    assert offer.json()["pc_id"] == "server-peer"
    assert handler.offer_request.sdp == "offer"


def test_offer_with_unknown_session_id_returns_404(client) -> None:
    response = client.post("/api/voice/sessions/unknown/offer", json={"sdp": "offer", "type": "offer"})

    assert response.status_code == 404


def test_invalid_offer_returns_422_and_cleans_up_session(app, client) -> None:
    created = client.post("/api/voice/sessions").json()

    response = client.post(f"/api/voice/sessions/{created['session_id']}/offer", json={"type": "offer"})

    assert response.status_code == 422
    assert asyncio.run(app.state.voice_sessions.get(created["session_id"])) is None


def test_failed_offer_cleans_up_server_owned_session(app, client) -> None:
    created = client.post("/api/voice/sessions").json()
    session = asyncio.run(app.state.voice_sessions.get(created["session_id"]))
    assert session is not None
    handler = FailingOfferHandler()
    session.request_handler = handler

    response = client.post(
        f"/api/voice/sessions/{created['session_id']}/offer",
        json={"sdp": "test", "type": "offer"},
    )

    assert response.status_code == 502
    assert handler.closed is True
    assert asyncio.run(app.state.voice_sessions.get(created["session_id"])) is None


def test_ice_candidate_patch_after_a_successful_offer_is_forwarded_to_the_session_handler(app, client) -> None:
    created = client.post("/api/voice/sessions").json()
    session = asyncio.run(app.state.voice_sessions.get(created["session_id"]))
    assert session is not None
    handler = PatchRecordingHandler()
    async def handle_web_request(request, _attach) -> dict[str, str]:
        handler.offer_request = request
        return {"sdp": "answer", "type": "answer", "pc_id": "server-peer"}

    handler.handle_web_request = handle_web_request
    session.request_handler = handler

    offer = client.post(
        f"/api/voice/sessions/{created['session_id']}/offer",
        json={"sdp": "offer", "type": "offer"},
    )
    assert offer.status_code == 200

    response = client.patch(
        f"/api/voice/sessions/{created['session_id']}/offer",
        json={
            "pc_id": "browser-peer",
            "candidates": [
                {"candidate": "candidate:1 1 UDP 1 127.0.0.1 5000 typ host", "sdp_mid": "0", "sdp_mline_index": 0}
            ],
        },
    )

    assert response.status_code == 204
    assert handler.patch_request.pc_id == "browser-peer"
    assert handler.patch_request.candidates[0].sdp_mid == "0"


def test_delete_session_makes_followup_offer_and_ice_requests_return_404(client) -> None:
    created = client.post("/api/voice/sessions").json()

    deleted = client.delete(f"/api/voice/sessions/{created['session_id']}")
    offer = client.post(
        f"/api/voice/sessions/{created['session_id']}/offer",
        json={"sdp": "offer", "type": "offer"},
    )
    patch = client.patch(
        f"/api/voice/sessions/{created['session_id']}/offer",
        json={"pc_id": "browser-peer", "candidates": []},
    )

    assert deleted.status_code == 204
    assert offer.status_code == 404
    assert patch.status_code == 404


def test_ice_patch_cors_preflight_is_allowed(client) -> None:
    response = client.options(
        "/api/voice/sessions/any/offer",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]
