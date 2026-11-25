from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.api.dependencies import get_session
from app.db.models import Appointment
from app.domain.appointments import check_doctor_availability, get_doctors
from app.schemas.dashboard import DashboardAppointmentResponse, DoctorResponse, SlotResponse

router = APIRouter(tags=["dashboard"])


@router.get("/doctors", response_model=list[DoctorResponse])
def list_doctors(
    specialty: str | None = Query(default=None), session: Session = Depends(get_session)
) -> list[DoctorResponse]:
    return get_doctors(session, specialty)


@router.get("/slots", response_model=list[SlotResponse])
def list_available_slots(
    doctor_id: int | None = Query(default=None, gt=0),
    date: date | None = Query(default=None),
    specialty: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[SlotResponse]:
    return check_doctor_availability(session, doctor_id, date, specialty)


@router.get("/appointments", response_model=list[DashboardAppointmentResponse])
def list_dashboard_appointments(session: Session = Depends(get_session)) -> list[Appointment]:
    """Dashboard view only; phone numbers are masked by the response schema."""
    statement = (
        select(Appointment)
        .options(joinedload(Appointment.doctor))
        .order_by(Appointment.appointment_date, Appointment.start_time)
    )
    return list(session.scalars(statement))
