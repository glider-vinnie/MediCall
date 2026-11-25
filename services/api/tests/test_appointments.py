from datetime import date, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Appointment, Doctor, Slot
from app.db.seed import seed_database
from app.domain.appointments import (
    book_appointment,
    cancel_appointment,
    check_doctor_availability,
    get_appointments_by_phone,
    get_my_appointments,
)
from app.domain.errors import ConflictError, NotFoundError, ValidationError, VerificationRequiredError
from app.domain.phone import CallSessionPhoneVerification


def verified_caller(phone: str = "9876543210") -> CallSessionPhoneVerification:
    caller = CallSessionPhoneVerification()
    caller.capture_spoken_phone(phone)
    assert caller.confirm_phone("yes") is True
    return caller


def first_available_slot(session: Session) -> Slot:
    slot = check_doctor_availability(session)[0]
    session.commit()  # Finish the read transaction before invoking a write service.
    return slot


def test_doctor_listing_is_seeded_and_filterable(client) -> None:
    response = client.get("/api/doctors")

    assert response.status_code == 200
    assert len(response.json()) == 6
    assert {doctor["specialty"] for doctor in response.json()} == {
        "Cardiologist",
        "Dermatologist",
        "General Physician",
        "Neurologist",
        "Orthopaedic",
        "Paediatrician",
    }
    filtered = client.get("/api/doctors", params={"specialty": "Cardiologist"})
    assert [doctor["name"] for doctor in filtered.json()] == ["Dr. Ananya Mehta"]


def test_seeding_is_idempotent(session: Session) -> None:
    seed_database(session)
    seed_database(session)

    assert len(session.scalars(select(Doctor)).all()) == 6
    assert len(session.scalars(select(Slot)).all()) == 210


def test_slot_availability_supports_doctor_and_specialty_filters(client) -> None:
    doctor = client.get("/api/doctors", params={"specialty": "Dermatologist"}).json()[0]
    response = client.get("/api/slots", params={"doctor_id": doctor["id"], "specialty": "Dermatologist"})

    assert response.status_code == 200
    assert response.json()
    assert all(slot["doctor_id"] == doctor["id"] for slot in response.json())
    assert all(slot["status"] == "available" for slot in response.json())


def test_successful_booking_requires_verified_context_and_persists(session: Session) -> None:
    slot = first_available_slot(session)

    appointment = book_appointment(session, verified_caller(), slot.id, patient_name="Asha Rao")

    assert appointment.status == "booked"
    assert appointment.phone_number == "+919876543210"
    assert session.get(Slot, slot.id).status == "booked"


def test_double_booking_is_rejected(session: Session) -> None:
    slot = first_available_slot(session)
    book_appointment(session, verified_caller("9876543210"), slot.id)

    with pytest.raises(ConflictError):
        book_appointment(session, verified_caller("9123456789"), slot.id)


def test_past_slots_cannot_be_booked(session: Session) -> None:
    doctor = session.scalar(select(Doctor))
    assert doctor is not None
    slot = Slot(
        doctor_id=doctor.id,
        appointment_date=date.today() - timedelta(days=1),
        start_time=time(9),
        end_time=time(9, 30),
        status="available",
    )
    session.add(slot)
    session.commit()

    with pytest.raises(ValidationError, match="future slot"):
        book_appointment(session, verified_caller(), slot.id)


def test_phone_based_appointment_retrieval_uses_normalized_number(session: Session) -> None:
    slot = first_available_slot(session)
    booked = book_appointment(session, verified_caller("9876543210"), slot.id)

    appointments = get_appointments_by_phone(session, "+91 98765 43210")
    mine = get_my_appointments(session, verified_caller("9876543210"))

    assert [appointment.id for appointment in appointments] == [booked.id]
    assert [appointment.id for appointment in mine] == [booked.id]


def test_successful_cancellation_releases_the_slot(session: Session) -> None:
    slot = first_available_slot(session)
    caller = verified_caller()
    booked = book_appointment(session, caller, slot.id)

    cancelled = cancel_appointment(session, caller, booked.id)

    assert cancelled.status == "cancelled"
    assert session.get(Slot, slot.id).status == "available"


def test_wrong_phone_cannot_cancel_an_appointment(session: Session) -> None:
    slot = first_available_slot(session)
    booked = book_appointment(session, verified_caller("9876543210"), slot.id)

    with pytest.raises(NotFoundError, match="verified phone"):
        cancel_appointment(session, verified_caller("9123456789"), booked.id)


def test_invalid_phone_is_rejected() -> None:
    caller = CallSessionPhoneVerification()

    with pytest.raises(ValidationError, match="valid phone"):
        caller.capture_spoken_phone("not a phone")


def test_unconfirmed_phone_cannot_book(session: Session) -> None:
    slot = first_available_slot(session)
    caller = CallSessionPhoneVerification()
    caller.capture_spoken_phone("9876543210")

    with pytest.raises(VerificationRequiredError):
        book_appointment(session, caller, slot.id)


def test_changing_phone_resets_verification() -> None:
    caller = verified_caller("9876543210")
    assert caller.digit_by_digit_readback() == "9 1 9 8 7 6 5 4 3 2 1 0"

    caller.capture_spoken_phone("9123456789")

    assert caller.is_verified is False
    with pytest.raises(VerificationRequiredError):
        caller.require_verified_phone()


def test_dashboard_masks_phone_numbers(client, session: Session) -> None:
    slot = first_available_slot(session)
    book_appointment(session, verified_caller(), slot.id)

    response = client.get("/api/appointments")

    assert response.status_code == 200
    appointment = response.json()[0]
    assert appointment["phone_number"] == "*********3210"
    assert "987654" not in appointment["phone_number"]
