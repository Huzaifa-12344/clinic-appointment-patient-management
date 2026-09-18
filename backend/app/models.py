import enum
from datetime import datetime, date, time
from sqlalchemy import String, DateTime, Date, Time, Boolean, ForeignKey, Text, Enum, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Role(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"

class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    no_show = "no_show"
    cancelled = "cancelled"
    rejected = "rejected"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    specialty: Mapped[str] = mapped_column(String(120), default="General Medicine")
    user = relationship("User")

class DoctorHours(Base):
    __tablename__ = "doctor_hours"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # Monday=0
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

class DoctorLeave(Base):
    __tablename__ = "doctor_leave"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True)
    leave_date: Mapped[date] = mapped_column(Date, index=True)
    __table_args__ = (Index("uq_doctor_leave_date", "doctor_id", "leave_date", unique=True),)

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.pending, index=True)
    visit_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

Index("uq_active_doctor_slot", Appointment.doctor_id, Appointment.start_time, unique=True,
      postgresql_where=Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]))
Index("uq_active_patient_time", Appointment.patient_id, Appointment.start_time, unique=True,
      postgresql_where=Appointment.status.in_([AppointmentStatus.pending, AppointmentStatus.confirmed]))
