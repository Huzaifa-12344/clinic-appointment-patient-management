from datetime import datetime, date, time
from pydantic import BaseModel, EmailStr, Field
from .models import AppointmentStatus, Role

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role

class DoctorCreate(BaseModel):
    full_name: str
    email: EmailStr
    specialty: str = "General Medicine"

class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

class LeaveIn(BaseModel):
    leave_date: date

class AppointmentIn(BaseModel):
    doctor_id: int
    start_time: datetime

class RescheduleIn(BaseModel):
    start_time: datetime

class NoteIn(BaseModel):
    note: str = Field(max_length=2000)
