# DoorStep — Smart Doorstep Vehicle Service

A car-service platform where a driver collects the customer's car from their door, a mechanic inspects and repairs it, and the customer tracks progress, approves extra repairs and pays an invoice.

- **Backend:** Django + Django REST Framework, JWT auth (`backend/`)
- **Frontend:** React 19 + Vite + Tailwind CSS (`client/`)
- **Database:** SQLite by default, MySQL optional

## Roles

| Role | Home page | What they do |
|---|---|---|
| Customer | `/app` | Add vehicles, book a pickup slot, track pickup and delivery, approve repairs, pay and download invoices, rate the service, see car health and service reminders. Hindi and Kannada available. |
| Service Center Manager | `/service-center` | Assign drivers and mechanics, manage bookings, analytics, invoices |
| Driver | `/driver` | Check the number plate, photograph the car, record the odometer, verify the pickup and delivery OTPs, share live location |
| Mechanic | `/mechanic` | Inspect cars, upload photo/video evidence, raise repair requests |
| Admin | `/admin` | Platform stats, analytics for any center, the repair-cost model, car catalog, all bookings and invoices |

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

Every demo account also has the password **`DoorStep@2026`** for normal email + password sign-in (local seed data only; re-seeding never overwrites a password that was changed).

With `OTP_BYPASS=True` (set in `.env.example`) the login page shows one-click demo buttons for these accounts. With it off, sign-in always uses a one-time code. Without SMS/email configured, the code is printed in the backend console (development only).

## Features at a glance

| Feature | Where | Notes |
|---|---|---|
| Pickup time slots | Book page; `GET /api/service-centers/<id>/slots/?date=` | Four windows a day, `slot_capacity` per center (Django admin). Up to 30 days ahead. |
| Return delivery | Driver: *Start Return Delivery* → *Hand Back Car*; customer sees the delivery OTP on Track | The delivery OTP completes the booking and issues the invoice. Managers can still mark *Collected at Center*. |
| Condition photos & odometer | Driver at pickup and delivery; customer's Track page | Before/after per side, and km driven while the center had the car. |
| Number plate check | Driver at pickup | OCR runs in the browser (tesseract.js); the backend matches it against the registration. Works on clear photos; glare, dirt and steep angles reduce accuracy. |
| Service reminders | Customer home page; `python manage.py send_service_reminders` | Due 6 months or 10,000 km after the last service. Run the command once a day (cron / Windows Task Scheduler). |
| Ratings & reviews | Customer: Track or History after completion | Centers show the real average or "new, no reviews yet". |
| PDF invoice + QR | Invoices → *Download PDF*; QR opens `/verify/<code>` | Code is signed with `SECRET_KEY`. Titled INVOICE, not TAX INVOICE: the app stores no GSTIN. |
| Analytics | Manager and admin → Analytics | Revenue, bookings, turnaround, top repairs, approval rate, ratings. |
| Learned cost estimator | Admin overview → *Repair cost model*; `python manage.py train_cost_model` | Used once 30+ completed, approved repairs exist; otherwise the rule formula. See below. |
| Email + password sign-in | Login, Register, Forgot password; key icon in the header to change password | Passwords are hashed by Django and must pass its strength rules. 5 wrong passwords lock the account for 15 minutes. "Forgot password" sends a 6-digit code by email/SMS. Sign-in with a one-time code still works. |
| Hindi / Kannada | Language menu (customer screens) | Navigation, home, booking, tracking, reminders, reviews. Staff screens stay in English. Translations need a native speaker's review. |

### The learned cost estimator, honestly

`train_cost_model` fits a ridge regression on the billed cost of approved repairs and prints a 5-fold
cross-validated comparison with the rule formula. With real repair history, that comparison is real
evidence. `python manage.py seed_repair_history --count 200` creates **synthetic** history only so the
pipeline can be demonstrated; a model trained on it only learns that made-up generator. The admin panel
and every estimate state the synthetic share, and synthetic jobs are hidden from analytics and booking lists.

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
| `FRONTEND_URL` | Public URL of the React app (invoice QR codes link to `FRONTEND_URL/verify/...`) |
| `OTP_BYPASS` | `False` — **never** enable in production; it allows signing in to any existing account without a code |
| `PAYMENT_GATEWAY` | Leave empty: online payment is turned off and customers pay at the service center. `mock` is a test gateway only — it moves no real money. |
| `TWILIO_*` and/or `EMAIL_*` | An SMS or email provider. Without one, OTP requests fail with an error in production. |
| `USE_MYSQL`, `DB_*` | Optional MySQL connection |

The frontend's `predev`/`prebuild` scripts copy the OCR engine and English language data from
`node_modules` into `client/public/ocr/`, so number plate reading never depends on a CDN.

## Payments

An invoice is created automatically when the service center manager marks a booking **Completed** (an admin or that center's manager can also regenerate it via `POST /api/bookings/<id>/generate-invoice/`). Invoices cannot be created before completion, and a paid invoice can no longer be changed.

Customers pay invoices from the Invoices page with UPI or card. Only a **mock gateway** exists today (`PAYMENT_GATEWAY=mock`, on by default in development): it records the payment and marks the invoice paid without charging anything, and the payment screen says so. Use `failure@mock` or card `4000 0000 0000 0002` to simulate a declined payment. Card numbers are validated (Luhn check) but only the last 4 digits are stored. A real gateway such as Razorpay plugs in at `backend/api/payment_service.py`.

## Live tracking

The driver dashboard posts the phone's GPS position every 10 seconds while "Enable GPS" is on. The customer's Track page shows the pickup point, service center and the driver's recent route on an OpenStreetMap map (Leaflet), refreshing every 10 seconds. The public OpenStreetMap tile servers are fine for development and light use; for production traffic, switch the tile URL in `client/src/components/LiveTrackingMap.tsx` to a tile provider.

## About the cost estimator

Until a learned model is trained (see above), the repair cost estimator is **rule-based**: base service price × severity multiplier × fuel-type adjustment, plus labour at ₹500/hour, shown as a range of 85–125% of that figure. See `backend/api/ai_cost_service.py`. Every estimate reports which method produced it.

## Project layout

```
backend/            Django project (config/) and the api app: models, views, services, tests
client/             React frontend
research_paper/     Benchmark script used for the accompanying paper
```
