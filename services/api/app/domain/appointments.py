from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import Appointment, Doctor, Slot
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.phone import CallSessionPhoneVerification, normalize_phone_number


def get_doctors(session: Session, specialty: str | None = None) -> list[Doctor]:
    statement = select(Doctor).order_by(Doctor.specialty, Doctor.name)
    if specialty:
        statement = statement.where(Doctor.specialty.ilike(specialty.strip()))
    return list(session.scalars(statement))


def check_doctor_availability(
    session: Session,
    doctor_id: int | None = None,
    appointment_date: date | None = None,
    specialty: str | None = None,
) -> list[Slot]:
    statement = (
        select(Slot)
        .join(Slot.doctor)
        .options(joinedload(Slot.doctor))
        .where(Slot.status == "available", Slot.appointment_date >= date.today())
        .order_by(Slot.appointment_date, Slot.start_time)
    )
    if doctor_id is not None:
        statement = statement.where(Slot.doctor_id == doctor_id)
    if appointment_date is not None:
        statement = statement.where(Slot.appointment_date == appointment_date)
    if specialty:
        statement = statement.where(Doctor.specialty.ilike(specialty.strip()))
    return list(session.scalars(statement))


def _assert_bookable(slot: Slot) -> None:
    starts_at = datetime.combine(slot.appointment_date, slot.start_time)
    if starts_at <= datetime.now():
        raise ValidationError("Appointments must be booked for a future slot.")


def book_appointment(
    session: Session,
    caller: CallSessionPhoneVerification,
    slot_id: int,
    patient_name: str | None = None,
) -> Appointment:
    phone_number = caller.require_verified_phone()
    if patient_name is not None and not patient_name.strip():
        patient_name = None
    try:
        with session.begin():
            slot = session.get(Slot, slot_id)
            if slot is None:
                raise NotFoundError("The requested appointment slot was not found.")
            _assert_bookable(slot)
            claimed = session.execute(
                update(Slot).where(Slot.id == slot_id, Slot.status == "available").values(status="booked")
            )
            if claimed.rowcount != 1:
                raise ConflictError("That appointment slot is no longer available.")
            appointment = Appointment(
                doctor_id=slot.doctor_id,
                slot_id=slot.id,
                patient_name=patient_name.strip() if patient_name else None,
                phone_number=phone_number,
                appointment_date=slot.appointment_date,
                start_time=slot.start_time,
                status="booked",
            )
            session.add(appointment)
        return appointment
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("That appointment slot is no longer available.") from error


def get_appointments_by_phone(session: Session, phone_number: str) -> list[Appointment]:
    normalized = normalize_phone_number(phone_number)
    statement = (
        select(Appointment)
        .options(joinedload(Appointment.doctor))
        .where(Appointment.phone_number == normalized)
        .order_by(Appointment.appointment_date, Appointment.start_time)
    )
    return list(session.scalars(statement))


def get_my_appointments(session: Session, caller: CallSessionPhoneVerification) -> list[Appointment]:
    return get_appointments_by_phone(session, caller.require_verified_phone())


def cancel_appointment(
    session: Session, caller: CallSessionPhoneVerification, appointment_id: int
) -> Appointment:
    phone_number = caller.require_verified_phone()
    with session.begin():
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise NotFoundError("The requested appointment was not found.")
        if appointment.phone_number != phone_number:
            raise NotFoundError("No matching appointment was found for the verified phone number.")
        if appointment.status != "booked":
            raise ConflictError("That appointment has already been cancelled.")
        appointment.status = "cancelled"
        released = session.execute(
            update(Slot).where(Slot.id == appointment.slot_id, Slot.status == "booked").values(status="available")
        )
        if released.rowcount != 1:
            raise ConflictError("The appointment slot could not be released.")
    return appointment
