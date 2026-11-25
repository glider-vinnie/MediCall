from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Doctor, Slot

DOCTORS = (
    {"name": "Dr. Ananya Mehta", "specialty": "Cardiologist", "qualification": "MBBS, MD, DM Cardiology", "experience_years": 14, "consultation_fee": 1100, "description": "Preventive and interventional cardiac care."},
    {"name": "Dr. Rohan Iyer", "specialty": "Dermatologist", "qualification": "MBBS, MD Dermatology", "experience_years": 10, "consultation_fee": 850, "description": "Skin, hair, and allergy-focused consultations."},
    {"name": "Dr. Kavya Nair", "specialty": "General Physician", "qualification": "MBBS, MD Internal Medicine", "experience_years": 12, "consultation_fee": 700, "description": "Comprehensive adult primary care."},
    {"name": "Dr. Arjun Malhotra", "specialty": "Neurologist", "qualification": "MBBS, MD, DM Neurology", "experience_years": 16, "consultation_fee": 1300, "description": "Headache, epilepsy, and neurological care."},
    {"name": "Dr. Neel Shah", "specialty": "Orthopaedic", "qualification": "MBBS, MS Orthopaedics", "experience_years": 11, "consultation_fee": 950, "description": "Bone, joint, sports, and mobility care."},
    {"name": "Dr. Priya Menon", "specialty": "Paediatrician", "qualification": "MBBS, MD Paediatrics", "experience_years": 13, "consultation_fee": 800, "description": "Compassionate child and adolescent care."},
)


def seed_database(session: Session) -> None:
    """Create the stable demo catalogue and future availability without duplicates."""
    doctors: list[Doctor] = []
    for payload in DOCTORS:
        doctor = session.scalar(select(Doctor).where(Doctor.name == payload["name"]))
        if doctor is None:
            doctor = Doctor(**payload)
            session.add(doctor)
            session.flush()
        doctors.append(doctor)

    start_day = date.today() + timedelta(days=1)
    for day_offset in range(7):
        appointment_day = start_day + timedelta(days=day_offset)
        for doctor in doctors:
            for start_hour in (9, 10, 11, 14, 15):
                starts_at = time(start_hour, 0)
                exists = session.scalar(
                    select(Slot.id).where(
                        Slot.doctor_id == doctor.id,
                        Slot.appointment_date == appointment_day,
                        Slot.start_time == starts_at,
                    )
                )
                if exists is None:
                    session.add(
                        Slot(
                            doctor_id=doctor.id,
                            appointment_date=appointment_day,
                            start_time=starts_at,
                            end_time=time(start_hour, 30),
                            status="available",
                        )
                    )
    session.commit()
