# DoorStep — Smart Doorstep Vehicle Service

A car-service platform where a driver collects the customer's car from their door, a mechanic inspects and repairs it, and the customer tracks progress, approves extra repairs and pays an invoice.

- **Backend:** Django + Django REST Framework, JWT auth (`backend/`)
- **Frontend:** React 19 + Vite + Tailwind CSS (`client/`)
- **Database:** SQLite by default, MySQL optional

## Roles

| Role | Home page | What they do |
|---|---|---|
| Customer | `/app` | Add vehicles, book services, track pickup, approve repairs, view invoices and car health |
| Service Center Manager | `/service-center` | Assign drivers and mechanics, manage bookings, generate invoices |
| Driver | `/driver` | Pick up cars, verify the handover OTP with the customer, share live location |
| Mechanic | `/mechanic` | Inspect cars, upload photo/video evidence, raise repair requests |
| Admin | `/admin` | Platform stats, car catalog, all bookings and invoices |

Anyone who signs up gets a **Customer** account. Staff accounts are created by an admin (Django admin at `/admin/` on the backend) or by the seed script.

## Run it locally

Requires Python 3.12+ (current Django releases need it) and Node.js 20.19+ (Vite 7).

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt
npm install
npm install --prefix client

# 2. Local settings (turns on DEBUG and demo login)
cp backend/.env.example backend/.env
cp client/.env.example client/.env      # optional: Google Maps key

# 3. Database and demo data
npm run migrate:django
npm run seed

# 4. Start backend (port 8000) and frontend (port 5173)
npm run dev
```

Open http://localhost:5173. The scripts call `python`; if your system only has `python3`, run the commands in `package.json` with `python3` instead.

### Demo accounts

`npm run seed` creates one account per role:

| Role | Email |
|---|---|
| Admin | admin@smartdoorstep.com |
| Manager | manager@smartdoorstep.com |
| Driver | driver@smartdoorstep.com |
| Mechanic | mechanic@smartdoorstep.com |
| Customer | customer@smartdoorstep.com |

With `OTP_BYPASS=True` (set in `.env.example`) the login page shows one-click demo buttons for these accounts. With it off, sign-in always uses a one-time code. Without SMS/email configured, the code is printed in the backend console (development only).

## Tests

```bash
cd backend && python manage.py test api     # backend tests
npm run build                               # type-checks and builds the frontend
```

## Deploying to production

Set these in `backend/.env` (or the server environment):

| Variable | Value |
|---|---|
| `DEBUG` | `False` |
| `SECRET_KEY` | A long random value: `python -c "import secrets; print(secrets.token_urlsafe(50))"`. The server refuses to start without one. |
| `ALLOWED_HOSTS` | Your API domain(s), comma-separated |
| `CORS_ALLOWED_ORIGINS` | Your frontend URL(s), e.g. `https://app.example.com` |
| `OTP_BYPASS` | `False` — **never** enable in production; it allows signing in to any existing account without a code |
| `TWILIO_*` and/or `EMAIL_*` | An SMS or email provider. Without one, OTP requests fail with an error in production. |
| `USE_MYSQL`, `DB_*` | Optional MySQL connection |

## About the cost estimator

The repair cost estimator is **rule-based**, not machine learning: base service price × severity multiplier × fuel-type adjustment, plus labour at ₹500/hour, shown as a range of 85–125% of that figure. See `backend/api/ai_cost_service.py`.

## Project layout

```
backend/            Django project (config/) and the api app: models, views, services, tests
client/             React frontend
research_paper/     Benchmark script used for the accompanying paper
```
