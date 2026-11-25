from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


def mask_phone_number(phone_number: str) -> str:
    if len(phone_number) <= 4:
        return "*" * len(phone_number)
    return f"{'*' * (len(phone_number) - 4)}{phone_number[-4:]}"


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialty: str
    qualification: str
    experience_years: int
    consultation_fee: Decimal
    description: str


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: str
    doctor: DoctorResponse


class DashboardAppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    slot_id: int
    patient_name: str | None
    phone_number: str
    appointment_date: date
    start_time: time
    status: str
    created_at: datetime
    doctor: DoctorResponse

    @field_serializer("phone_number")
    def serialize_phone_number(self, phone_number: str) -> str:
        return mask_phone_number(phone_number)
