from datetime import datetime, timedelta, timezone, date as date_type
import secrets
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, get_db
from .models import User, Role, DoctorProfile, DoctorHours, DoctorLeave, Appointment, AppointmentStatus
from .schemas import RegisterIn, LoginIn, TokenOut, DoctorCreate, HoursIn, LeaveIn, AppointmentIn, RescheduleIn, NoteIn
from .security import hash_password, verify_password, create_token, current_user, require_role, automation_auth
from .email_events import emit_email

app = FastAPI(title="Nowshera Family Clinic API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if not db.scalar(select(User).where(User.role == Role.admin)):
            db.add(User(email="admin@clinic.local", full_name="Clinic Admin", password_hash=hash_password("Admin123!"), role=Role.admin))
            db.commit()

@app.get("/health")
def health(): return {"ok": True}

@app.post("/auth/register", response_model=TokenOut)
def register(body:RegisterIn, db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,"Email is already registered")
    u=User(email=body.email.lower(),full_name=body.full_name,password_hash=hash_password(body.password),role=Role.patient)
    db.add(u);db.commit();db.refresh(u)
    return TokenOut(access_token=create_token(u),role=u.role)

@app.post("/auth/login", response_model=TokenOut)
def login(body:LoginIn, db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==body.email.lower()))
    if not u or not verify_password(body.password,u.password_hash): raise HTTPException(401,"Invalid email or password")
    if not u.active: raise HTTPException(403,"Account is inactive")
    return TokenOut(access_token=create_token(u),role=u.role)

@app.get("/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"email":u.email,"name":u.full_name,"role":u.role}

@app.get("/doctors")
def doctors(db:Session=Depends(get_db)):
    rows=db.execute(select(DoctorProfile,User).join(User,User.id==DoctorProfile.user_id).where(User.active==True)).all()
    return [{"id":p.id,"name":u.full_name,"specialty":p.specialty} for p,u in rows]

@app.post("/admin/doctors")
async def add_doctor(body:DoctorCreate, admin:User=Depends(require_role(Role.admin)), db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,"Email is already registered")
    temp=secrets.token_urlsafe(10)
    u=User(email=body.email.lower(),full_name=body.full_name,password_hash=hash_password(temp),role=Role.doctor)
    db.add(u);db.flush();p=DoctorProfile(user_id=u.id,specialty=body.specialty);db.add(p);db.commit();db.refresh(p)
    await emit_email("doctor_invite",u.email,u.full_name,temporary_password=temp)
    return {"id":p.id,"message":"Doctor created; invitation email queued"}

@app.patch("/admin/doctors/{doctor_id}/active")
def doctor_active(doctor_id:int, active:bool=Query(...), admin:User=Depends(require_role(Role.admin)), db:Session=Depends(get_db)):
    p=db.get(DoctorProfile,doctor_id)
    if not p: raise HTTPException(404,"Doctor not found")
    u=db.get(User,p.user_id);u.active=active;db.commit()
    return {"active":active}

def profile(u:User,db:Session):
    p=db.scalar(select(DoctorProfile).where(DoctorProfile.user_id==u.id))
    if not p: raise HTTPException(404,"Doctor profile not found")
    return p

@app.post("/doctor/hours")
def add_hours(body:HoursIn,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    if body.end_time<=body.start_time: raise HTTPException(400,"End time must be after start time")
    p=profile(u,db)
    rows=db.scalars(select(DoctorHours).where(DoctorHours.doctor_id==p.id,DoctorHours.weekday==body.weekday)).all()
    if any(body.start_time<x.end_time and body.end_time>x.start_time for x in rows): raise HTTPException(409,"Working hours overlap an existing range")
    r=DoctorHours(doctor_id=p.id,**body.model_dump());db.add(r);db.commit();db.refresh(r)
    return {"id":r.id}

@app.get("/doctor/hours")
def get_hours(u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    p=profile(u,db);rows=db.scalars(select(DoctorHours).where(DoctorHours.doctor_id==p.id)).all()
    return [{"id":r.id,"weekday":r.weekday,"start_time":str(r.start_time),"end_time":str(r.end_time)} for r in rows]

@app.post("/doctor/leave")
async def leave(body:LeaveIn,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    if body.leave_date<datetime.now(timezone.utc).date(): raise HTTPException(400,"Leave day cannot be in the past")
    p=profile(u,db)
    if db.scalar(select(DoctorLeave).where(DoctorLeave.doctor_id==p.id,DoctorLeave.leave_date==body.leave_date)): raise HTTPException(409,"Leave day already exists")
    db.add(DoctorLeave(doctor_id=p.id,leave_date=body.leave_date))
    lo=datetime.combine(body.leave_date,datetime.min.time(),tzinfo=timezone.utc);hi=lo+timedelta(days=1)
    rows=db.scalars(select(Appointment).where(Appointment.doctor_id==p.id,Appointment.start_time>=lo,Appointment.start_time<hi,Appointment.status.in_([AppointmentStatus.pending,AppointmentStatus.confirmed]))).all()
    for a in rows:a.status=AppointmentStatus.cancelled
    db.commit()
    for a in rows:
        patient=db.get(User,a.patient_id)
        await emit_email("cancelled",patient.email,patient.full_name,reason="Doctor leave",start_time=a.start_time.isoformat())
    return {"cancelled_appointments":len(rows)}

def bookable(doctor_id:int,start:datetime,db:Session):
    if start.tzinfo is None:start=start.replace(tzinfo=timezone.utc)
    now=datetime.now(timezone.utc)
    if start<=now:raise HTTPException(400,"Past slots cannot be booked")
    p=db.get(DoctorProfile,doctor_id)
    if not p:raise HTTPException(404,"Doctor not found")
    if not db.get(User,p.user_id).active:raise HTTPException(400,"Doctor is inactive")
    if start.minute not in (0,30) or start.second!=0:raise HTTPException(400,"Appointments must start on a 30-minute boundary")
    if db.scalar(select(DoctorLeave).where(DoctorLeave.doctor_id==doctor_id,DoctorLeave.leave_date==start.date())):raise HTTPException(400,"Doctor is on leave")
    hours=db.scalars(select(DoctorHours).where(DoctorHours.doctor_id==doctor_id,DoctorHours.weekday==start.weekday())).all()
    end=start+timedelta(minutes=30)
    if not any(start.time()>=h.start_time and end.time()<=h.end_time for h in hours):raise HTTPException(400,"Requested time is outside doctor working hours")
    return end

@app.get("/doctors/{doctor_id}/slots")
def slots(doctor_id:int,day:date_type,db:Session=Depends(get_db)):
    if day<datetime.now(timezone.utc).date():return []
    if db.scalar(select(DoctorLeave).where(DoctorLeave.doctor_id==doctor_id,DoctorLeave.leave_date==day)):return []
    p=db.get(DoctorProfile,doctor_id)
    if not p or not db.get(User,p.user_id).active:return []
    hrs=db.scalars(select(DoctorHours).where(DoctorHours.doctor_id==doctor_id,DoctorHours.weekday==day.weekday())).all()
    active=set(db.scalars(select(Appointment.start_time).where(Appointment.doctor_id==doctor_id,Appointment.status.in_([AppointmentStatus.pending,AppointmentStatus.confirmed]))).all())
    out=[]
    for h in hrs:
        cur=datetime.combine(day,h.start_time,tzinfo=timezone.utc);stop=datetime.combine(day,h.end_time,tzinfo=timezone.utc)
        while cur+timedelta(minutes=30)<=stop:
            if cur>datetime.now(timezone.utc) and cur not in active:out.append(cur.isoformat())
            cur+=timedelta(minutes=30)
    return sorted(out)

@app.post("/appointments")
def book(body:AppointmentIn,u:User=Depends(require_role(Role.patient)),db:Session=Depends(get_db)):
    start=body.start_time if body.start_time.tzinfo else body.start_time.replace(tzinfo=timezone.utc)
    end=bookable(body.doctor_id,start,db)
    a=Appointment(patient_id=u.id,doctor_id=body.doctor_id,start_time=start,end_time=end,status=AppointmentStatus.pending);db.add(a)
    try:db.commit();db.refresh(a)
    except IntegrityError:
        db.rollback();raise HTTPException(409,"That doctor slot is taken or you already have another appointment at the same time")
    return {"id":a.id,"status":a.status}

@app.get("/appointments")
def appointments(u:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(Appointment)
    if u.role==Role.patient:q=q.where(Appointment.patient_id==u.id)
    elif u.role==Role.doctor:q=q.where(Appointment.doctor_id==profile(u,db).id)
    rows=db.scalars(q.order_by(Appointment.start_time.desc())).all()
    return [{"id":a.id,"patient_id":a.patient_id,"doctor_id":a.doctor_id,"start_time":a.start_time,"status":a.status,"visit_note":a.visit_note if u.role!=Role.admin else None} for a in rows]

def owned(aid:int,u:User,db:Session):
    a=db.get(Appointment,aid)
    if not a:raise HTTPException(404,"Appointment not found")
    if u.role==Role.patient and a.patient_id!=u.id:raise HTTPException(403,"Access denied")
    if u.role==Role.doctor and a.doctor_id!=profile(u,db).id:raise HTTPException(403,"Access denied")
    return a

@app.post("/appointments/{aid}/confirm")
async def confirm(aid:int,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if a.status!=AppointmentStatus.pending:raise HTTPException(400,"Only Pending appointments can be confirmed")
    a.status=AppointmentStatus.confirmed;db.commit();p=db.get(User,a.patient_id)
    await emit_email("confirmed",p.email,p.full_name,start_time=a.start_time.isoformat())
    return {"status":a.status}

@app.post("/appointments/{aid}/reject")
async def reject(aid:int,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if a.status!=AppointmentStatus.pending:raise HTTPException(400,"Only Pending appointments can be rejected")
    a.status=AppointmentStatus.rejected;db.commit();p=db.get(User,a.patient_id)
    await emit_email("rejected",p.email,p.full_name,start_time=a.start_time.isoformat())
    return {"status":a.status}

@app.post("/appointments/{aid}/cancel")
async def cancel(aid:int,u:User=Depends(require_role(Role.patient)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if a.status not in [AppointmentStatus.pending,AppointmentStatus.confirmed]:raise HTTPException(400,"Appointment cannot be cancelled")
    if a.start_time-datetime.now(timezone.utc)<=timedelta(hours=2):raise HTTPException(400,"Cancellation is blocked within 2 hours")
    a.status=AppointmentStatus.cancelled;db.commit()
    await emit_email("cancelled",u.email,u.full_name,start_time=a.start_time.isoformat())
    return {"status":a.status}

@app.post("/appointments/{aid}/reschedule")
def reschedule(aid:int,body:RescheduleIn,u:User=Depends(require_role(Role.patient)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if a.start_time-datetime.now(timezone.utc)<=timedelta(hours=2):raise HTTPException(400,"Reschedule is blocked within 2 hours")
    start=body.start_time if body.start_time.tzinfo else body.start_time.replace(tzinfo=timezone.utc)
    end=bookable(a.doctor_id,start,db);a.start_time=start;a.end_time=end;a.status=AppointmentStatus.pending
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,"New slot is not available")
    return {"status":a.status,"start_time":a.start_time}

@app.post("/appointments/{aid}/complete")
def complete(aid:int,body:NoteIn,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if datetime.now(timezone.utc)<a.start_time:raise HTTPException(400,"A future visit cannot be completed")
    a.status=AppointmentStatus.completed;a.visit_note=body.note;db.commit();return {"status":a.status}

@app.post("/appointments/{aid}/no-show")
def no_show(aid:int,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    a=owned(aid,u,db)
    if datetime.now(timezone.utc)<a.start_time:raise HTTPException(400,"A future visit cannot be marked No-show")
    a.status=AppointmentStatus.no_show;db.commit();return {"status":a.status}

@app.get("/doctor/patients/{patient_id}/history")
def history(patient_id:int,u:User=Depends(require_role(Role.doctor)),db:Session=Depends(get_db)):
    p=profile(u,db);rows=db.scalars(select(Appointment).where(Appointment.patient_id==patient_id,Appointment.doctor_id==p.id).order_by(Appointment.start_time.desc())).all()
    return [{"id":a.id,"start_time":a.start_time,"status":a.status,"visit_note":a.visit_note} for a in rows]

@app.get("/admin/dashboard")
def dashboard(admin:User=Depends(require_role(Role.admin)),db:Session=Depends(get_db)):
    today=datetime.now(timezone.utc).date();lo=datetime.combine(today,datetime.min.time(),tzinfo=timezone.utc);hi=lo+timedelta(days=1)
    ds=db.execute(select(DoctorProfile,User).join(User,User.id==DoctorProfile.user_id)).all();out=[]
    for p,u in ds:
        counts={s.value:0 for s in AppointmentStatus}
        for s,c in db.execute(select(Appointment.status,func.count()).where(Appointment.doctor_id==p.id).group_by(Appointment.status)).all():counts[s.value]=c
        out.append({"doctor_id":p.id,"name":u.full_name,"active":u.active,"counts":counts})
    rows=db.scalars(select(Appointment).where(Appointment.start_time>=lo,Appointment.start_time<hi).order_by(Appointment.start_time)).all()
    return {"today":[{"id":a.id,"doctor_id":a.doctor_id,"start_time":a.start_time,"status":a.status} for a in rows],"doctors":out}

@app.post("/internal/automation/expire-pending",dependencies=[Depends(automation_auth)])
async def expire(db:Session=Depends(get_db)):
    rows=db.scalars(select(Appointment).where(Appointment.status==AppointmentStatus.pending,Appointment.start_time<=datetime.now(timezone.utc))).all()
    for a in rows:a.status=AppointmentStatus.cancelled
    db.commit()
    for a in rows:
        p=db.get(User,a.patient_id);await emit_email("cancelled",p.email,p.full_name,reason="Not confirmed before start time",start_time=a.start_time.isoformat())
    return {"cancelled":len(rows)}

@app.post("/internal/automation/reminders",dependencies=[Depends(automation_auth)])
async def reminders(db:Session=Depends(get_db)):
    now=datetime.now(timezone.utc);lo=now+timedelta(hours=23);hi=now+timedelta(hours=25)
    rows=db.scalars(select(Appointment).where(Appointment.status==AppointmentStatus.confirmed,Appointment.reminder_sent==False,Appointment.start_time>=lo,Appointment.start_time<=hi)).all()
    for a in rows:a.reminder_sent=True
    db.commit()
    for a in rows:
        p=db.get(User,a.patient_id);await emit_email("reminder",p.email,p.full_name,start_time=a.start_time.isoformat())
    return {"reminders":len(rows)}
