from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Time, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    specialty: Mapped[str] = mapped_column("speciality", String(80), index=True)
    qualification: Mapped[str] = mapped_column(String(160))
    experience_years: Mapped[int] = mapped_column(Integer)
    consultation_fee: Mapped[float] = mapped_column(Numeric(10, 2))
    description: Mapped[str] = mapped_column(String(500))

    slots: Mapped[list["Slot"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")

    __table_args__ = (CheckConstraint("experience_years >= 0", name="ck_doctor_experience_nonnegative"),)


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    appointment_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(16), default="available", index=True)

    doctor: Mapped[Doctor] = relationship(back_populates="slots")
    appointment: Mapped["Appointment | None"] = relationship(back_populates="slot", uselist=False)

    __table_args__ = (
        UniqueConstraint("doctor_id", "appointment_date", "start_time", name="uq_slot_doctor_start"),
        CheckConstraint("status IN ('available', 'booked')", name="ck_slot_status"),
        CheckConstraint("end_time > start_time", name="ck_slot_end_after_start"),
        Index("ix_slots_doctor_date_status", "doctor_id", "appointment_date", "status"),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="RESTRICT"), unique=True, index=True)
    patient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(20), index=True)
    appointment_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(16), default="booked", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
    slot: Mapped[Slot] = relationship(back_populates="appointment")

    __table_args__ = (
        CheckConstraint("status IN ('booked', 'cancelled')", name="ck_appointment_status"),
        Index("ix_appointments_phone_status", "phone_number", "status"),
    )
