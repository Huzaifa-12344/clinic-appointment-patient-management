# Clinic Appointment & Patient Management System

Full-stack project for **Nowshera Family Clinic**. Patients request appointments, doctors manage availability and visits, admins manage doctors and clinic-wide appointment totals, and n8n handles email/reminder automation.

## Stack
- **Frontend:** React + Vite, responsive mobile UI
- **Backend:** FastAPI + SQLAlchemy
- **Database:** PostgreSQL
- **Authentication:** JWT + bcrypt password hashing + server-side role checks
- **Automation:** n8n
- **Local email testing:** MailHog
- **Local orchestration:** Docker Compose

## Implemented rules
- Patient registration/login; admin/doctor/patient roles
- Admin creates doctors; doctor invitation email event
- Doctor weekly hours with invalid/overlap validation
- 30-minute free-slot generation
- Leave days block slots and automatically cancel active appointments
- Patient booking with PostgreSQL partial unique indexes to stop doctor double-booking and patient same-time double-booking
- Server rejects past, inactive-doctor, leave-day and outside-hours bookings
- Doctor confirms/rejects requests
- Patient cancel/reschedule only more than 2 hours before start
- Reschedule returns appointment to Pending and releases old slot
- Doctor can complete/no-show only after visit start
- Doctor-patient history is scoped to that doctor
- Visit notes are visible only to patient and doctor; admin dashboard excludes notes
- Pending appointments auto-cancel after start via automation endpoint
- One-day-before reminders are idempotent using `reminder_sent`
- Responsive mobile layout

## Quick start
1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Start everything:
   ```bash
   docker compose up --build
   ```
3. Open:
   - Website: http://localhost:5173
   - API docs: http://localhost:8000/docs
   - n8n: http://localhost:5678
   - MailHog inbox: http://localhost:8025
4. Import `automation/clinic-automation.json` into n8n.
5. In n8n create an SMTP credential named **MailHog SMTP** with host `mailhog`, port `1025`, no SSL/auth, then assign it to **Send Email**.
6. Activate the workflow.

### Default local admin
- Email: `admin@clinic.local`
- Password: `Admin123!`

Change this for any non-demo deployment.

## API security model
Every protected request is authorized on the server using the JWT user and role. Patient appointment access checks patient ownership. Doctor appointment/history access checks the doctor profile ID. Admin has aggregate/dashboard access but the private appointment-detail endpoint intentionally blocks admin access to visit notes.

## Test case mapping
| # | Brief case | Implementation |
|---|---|---|
| 1 | Book → doctor confirms → email | `/appointments`, `/confirm`, n8n webhook |
| 2 | Admin doctor + 9–11 hours → 4 slots + dashboard | `/admin/doctors`, `/doctor/hours`, `/slots`, `/admin/dashboard` |
| 3 | Same doctor slot / patient same-time blocked | PostgreSQL partial unique indexes + 409 |
| 4 | Outside hours / fully booked | `ensure_bookable()` + free-slot filtering |
| 5 | Past/inactive/early completion/leave | Server validations + leave cancellation |
| 6 | Cancel/reschedule cutoff and slot release | `/cancel`, `/reschedule`, 2-hour rule |
| 7 | Invalid/overlap hours, past leave | Validations in doctor endpoints |
| 8 | Wrong role | `require_role()` + doctor ownership check |
| 9 | Private records | `appointment_for_access()` + doctor-scoped history + admin note denial |
|10| Reminder + pending expiry + mobile | n8n scheduled API calls + responsive CSS |

## Production notes
For production, replace demo CORS (`*`), admin bootstrap password, JWT secret, automation key, MailHog, and n8n local SMTP with environment-specific secure values. Put API/web behind HTTPS, use managed Postgres backups, and restrict n8n/internal endpoints to a private network.
