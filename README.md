# DoorStep — Smart Doorstep Vehicle Service

A car-service platform where a driver collects the customer's car from their door, a mechanic inspects and repairs it, and the customer tracks progress, approves extra repairs and pays an invoice.

- **Backend:** Django + Django REST Framework, JWT auth (`backend/`)
- **Frontend:** React 19 + Vite + Tailwind CSS (`client/`)
- **Database:** SQLite by default, MySQL optional

## Roles

| Role | Home page | What they do |
|---|---|---|
| Customer | `/app` | Add vehicles, book a pickup slot, track pickup and delivery, approve repairs, pay and download invoices, rate the service, see car health and service reminders. Hindi and Kannada available. |
| Driver | `/driver` | Check the number plate, photograph the car, record the odometer, verify the pickup and delivery OTPs, share live location |
| Mechanic | `/mechanic` | Inspect cars, upload photo/video evidence, raise repair requests |
| Admin | `/admin` | Runs the service centers: confirm bookings, assign drivers and mechanics, add staff, invoices and analytics. Also platform stats, the repair-cost model and the car catalog. |

Anyone who signs up gets a **Customer** account. Drivers and mechanics are added by an admin on the **Staff** page; the seed script also creates one demo account per role.

## Run it locally (step by step, VS Code)

You need **Python 3.12+**, **Node.js 20.19+** and **Git**. Check with:

```bash
python --version      # Windows: if this fails, try  py --version
node --version
git --version
```

Open the project folder in VS Code (**File → Open Folder…**) and open a terminal with **Ctrl + `** (the key under Esc).
Every command below is run from the **project root folder** (the one containing `README.md`), unless a step says otherwise.

> **Using GitHub Copilot?** In Copilot Chat choose **Agent** mode and ask, for example:
> *"Follow the README section 'First-time setup' for Windows and run each command in the terminal."*
> Copilot will propose each command; read it and click **Continue** to run it.

### First-time setup (do this once)

**Step 1: create and activate a Python virtual environment.** It keeps this project's packages separate, and makes the `python` command work the same on every computer.

Windows (PowerShell, the VS Code default):
```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```
If PowerShell says *"running scripts is disabled on this system"*, run this once, then the activate line again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
When it is active, the terminal prompt starts with `(.venv)`. **Activate it again every time you open a new terminal.**
VS Code tip: **Ctrl + Shift + P → "Python: Select Interpreter" →** choose the one inside `.venv`, and new terminals activate it automatically.

**Step 2: install the packages**
```bash
pip install -r backend/requirements.txt
npm install
npm install --prefix client
```

**Step 3: create your settings files.** These files are never committed to Git.

Windows (PowerShell):
```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item client\.env.example client\.env
```
macOS / Linux:
```bash
cp backend/.env.example backend/.env
cp client/.env.example client/.env
```
Optional: open `backend/.env` and set `DEMO_ACCOUNT_PASSWORD=` to a password of your choice, so the demo accounts can also sign in with email + password (do this before Step 4).

**Step 4: create the database and the demo data**
```bash
npm run migrate:django
npm run seed
```

**Step 5: start the app**
```bash
npm run dev
```
This starts the backend at http://127.0.0.1:8000 and the website at **http://localhost:5173**. Open the website in your browser.
Stop it with **Ctrl + C** in the terminal.

### Every time after that
```bash
# Windows:  .venv\Scripts\Activate.ps1     macOS/Linux:  source .venv/bin/activate
npm run dev
```

### After `git pull` (when the code has changed)
```bash
git pull
pip install -r backend/requirements.txt
npm install
npm install --prefix client
npm run migrate:django
npm run dev
```

### Run the backend and frontend in separate terminals (optional)
Useful to see each one's messages separately. Use the **split terminal** button in VS Code.
```bash
# Terminal 1: backend (activate .venv first)
python backend/manage.py runserver 8000

# Terminal 2: frontend
npm run dev --prefix client
```

### Tests and checks
There are three kinds of automated tests. GitHub runs all of them on every pull request and on every push to `main` (the "CI" check, `.github/workflows/ci.yml`).

| Tests | What they cover | Command |
|---|---|---|
| Backend (Django) | API rules: bookings, slots, pickup/delivery codes, passwords, Google sign-in, payments, invoices, auto-assignment, ... | `python backend/manage.py test api` (should end with "OK") |
| Frontend unit (Vitest) | Small helpers: distances, road-route maths, ETAs, map arrow direction, simulated-drive spacing, sign-in routes | `npm test --prefix client` (with coverage: `npm run test:coverage --prefix client`) |
| Browser (Playwright) | The real app in Chrome: sign in, book a pickup on the map, the admin confirms and a driver is auto-assigned, the driver shares GPS or simulates the drive, the customer tracks it, an admin adds staff, and one booking goes through all four roles to a paid invoice | `npm run test:e2e --prefix client` |

The browser tests start their own backend and frontend (ports 8001 and 5174) with a fresh, seeded database in `client/e2e/.data/`. Your own database and running dev servers are not touched. The first time, download the test browser with:
```bash
cd client
npm run e2e:install-browser
cd ..
```

CI installs Python packages from `backend/requirements-ci.txt` (exact versions with checked hashes). After changing `backend/requirements*.txt`, regenerate it with the command at the top of that file.

Backend coverage report (which lines the tests run):
```bash
pip install -r backend/requirements-dev.txt
cd backend
coverage run manage.py test api
coverage report
cd ..
```

#### Test coverage in SonarCloud (optional, repository owner only)
CI already measures coverage (backend `coverage.xml`, frontend `lcov.info`). The **SonarCloud coverage** job sends it to SonarCloud once you switch it on; until then it is skipped with a note. To switch it on:
1. On sonarcloud.io, open the project → **Administration → Analysis Method** and turn **off** Automatic Analysis.
2. Under **Administration → Information**, check that the project key and organization key match `sonar-project.properties` (correct the file if not).
3. Create a token (**My Account → Security**) and add it on GitHub: repository **Settings → Secrets and variables → Actions → New repository secret**, name `SONAR_TOKEN`.

The next pull request then shows coverage on SonarCloud.

Other checks:
```bash
python backend/manage.py check        # Django configuration check
npm run build                         # type-checks and builds the frontend
```

### Useful extra commands
| What | Command |
|---|---|
| Create your own admin login for the Django admin site (http://127.0.0.1:8000/django-admin/) | `python backend/manage.py createsuperuser` |
| Send service reminders (run once a day) | `python backend/manage.py send_service_reminders` |
| Generate **synthetic** repair history to demo the learned cost estimator | `python backend/manage.py seed_repair_history --count 200` |
| Train the repair-cost model (needs 30+ completed repairs) | `python backend/manage.py train_cost_model` |
| See which database migrations are applied | `python backend/manage.py showmigrations api` |
| Re-run only the demo accounts seed | `python backend/manage.py seed_demo_accounts` |
| Preview the production build of the website | `npm run build` then `npm run preview --prefix client` |

### Start again with an empty database
This **deletes all local data** (bookings, accounts, invoices). Stop the app first (Ctrl + C).
```powershell
# Windows
Remove-Item backend\db.sqlite3
```
```bash
# macOS / Linux
rm backend/db.sqlite3
```
Then run `npm run migrate:django` and `npm run seed` again.

### Common problems
| Problem | Fix |
|---|---|
| `python` is not recognised / not found | Activate `.venv` (Step 1). On Windows, also try `py` instead of `python` |
| `ModuleNotFoundError: No module named 'django'` | The virtual environment is not active, or Step 2 was skipped. Activate `.venv` and run `pip install -r backend/requirements.txt` |
| `SECRET_KEY must be set when DEBUG is off` | `backend/.env` is missing. Do Step 3 |
| `Port 5173 is already in use` or `port 8000 is already in use` | The app is already running in another terminal. Close it with Ctrl + C, or close that terminal |
| `no such table` or `no such column` errors | Run `npm run migrate:django` |
| No "Sign in with Google" button | http://localhost:8000/api/health-check/ should show a `google_client_id`. It is empty only when `GOOGLE_CLIENT_ID=off` is set in `backend/.env`. An ad blocker can also hide the button. |
| Google says "Access blocked" / only test users can sign in | The Google client is still in *Testing*. In Google Cloud Console, add the Gmail address under **Test users**, or publish the app (OAuth consent screen / Audience → **Publish app**). |
| Google sign-in popup says "origin not allowed" / error 400 | In Google Cloud Console, add the exact frontend address (e.g. `http://localhost:5173`) under the OAuth client's **Authorized JavaScript origins**. Changes can take a few minutes. |
| The login page has no demo buttons | Open http://localhost:8000/api/health-check/. If `"demo_login"` is `false`, add `OTP_BYPASS=True` to `backend/.env` and restart. If the page doesn't open, the backend isn't running. (The sign-in page keeps checking for 2 minutes, so a backend that starts late is fine.) |
| A driver's phone says "Browsers only allow GPS on https://" | Use `npm run dev:phone` (see "Live tracking") |
| Number plate scanning fails | Run `npm install --prefix client` again, then restart `npm run dev` (it copies the OCR files into `client/public/ocr/`) |
| Address search on the Book page says it is unavailable | The free OpenStreetMap search needs internet (on the backend). Move the map under the pin, use "Use current location", or pick a preset area instead |
| The map area is blank or says it could not load | The map style and tiles come from `tiles.openfreemap.org`; check the internet connection (or a college firewall blocking it). If it says WebGL is off, turn on hardware acceleration in the browser settings |

### Demo accounts

`npm run seed` creates one account per role:

| Role | Email |
|---|---|
| Admin | admin@smartdoorstep.com |
| Driver | driver@smartdoorstep.com |
| Mechanic | mechanic@smartdoorstep.com |
| Customer | customer@smartdoorstep.com |

To also sign in to the demo accounts with email + password, set `DEMO_ACCOUNT_PASSWORD` in `backend/.env` to a password of your choice **before** running `npm run seed`. The seed gives each demo account that password, but only if the account has none yet, so a password that was changed is never reset. The password lives only in your `.env`, never in the code.

The sign-in page has a tab per role, each with its own address, so staff can bookmark theirs: `/login/customer`, `/login/driver`, `/login/mechanic`, `/login/admin`. Signing in on the wrong tab (for example a driver on the Customer tab) is refused, with a link to the right tab.

With `OTP_BYPASS=True` (set in `.env.example`) each tab shows a "Try the demo … account" button. With it off, people sign in with their password or with Google.

## Features at a glance

| Feature | Where | Notes |
|---|---|---|
| Pickup time slots | Book page; `GET /api/service-centers/<id>/slots/?date=` | Four windows a day, `slot_capacity` per center (Django admin). Up to 30 days ahead. |
| Return delivery | Driver: *Start Return Delivery* → *Hand Back Car*; customer sees the delivery OTP on Track | The delivery OTP completes the booking and issues the invoice. Admins can still mark *Collected at Center*. |
| Condition photos & odometer | Driver at pickup and delivery; customer's Track page | Before/after per side, and km driven while the center had the car. |
| Number plate check | Driver at pickup | OCR runs in the browser (tesseract.js); the backend matches it against the registration. Works on clear photos; glare, dirt and steep angles reduce accuracy. |
| Service reminders | Customer home page; `python manage.py send_service_reminders` | Due 6 months or 10,000 km after the last service. Run the command once a day (cron / Windows Task Scheduler). |
| Automatic staff assignment | Admin clicks **Confirm**; **Assign Staff** shows the ranked list | Driver = lowest *distance to the customer (km) + 3 km × pickups already that day*, among available drivers of that center who are free in the booking's time slot. Position = latest GPS if under 2 hours old, else the driver's service center. Mechanic = fewest open jobs. The manager can always pick someone else. Code: `backend/api/dispatch_service.py` |
| Ratings & reviews | Customer: Track or History after completion | Centers show the real average or "new, no reviews yet". |
| PDF invoice + QR | Invoices → *Download PDF*; QR opens `/verify/<code>` | Code is signed with `SECRET_KEY`. Titled INVOICE, not TAX INVOICE: the app stores no GSTIN. |
| Analytics | Admin → Analytics | Revenue, bookings, turnaround, top repairs, approval rate, ratings. |
| Learned cost estimator | Admin overview → *Repair cost model*; `python manage.py train_cost_model` | Used once 30+ completed, approved repairs exist; otherwise the rule formula. See below. |
| Email + password sign-in | Login, Register, Forgot password; key icon in the header to change password | Passwords are hashed by Django and must pass its strength rules. 5 wrong passwords lock the account for 15 minutes. |
| Contact number at booking | Booking form | The customer confirms the mobile number the driver should call (filled in from their profile). It is checked, stored on the booking, and shown to the driver and the admin. |
| Coupons | "Coupon code" on the booking form; create codes in the Django admin (`/django-admin/` → Coupons) | Percent or flat discounts with optional cap, minimum package price, dates, total uses and uses per customer. The discount is fixed at booking and comes off the package price before GST on the invoice. The demo seed adds `WELCOME10`. |
| Reschedule | "Reschedule pickup" on the Track page | While a booking is Pending or Confirmed, the customer can move it to any slot with room. The customer, the admins and the assigned driver are notified. |
| Browser alerts | Bell button in the header (needs `VAPID_*` keys) | Web Push: notifications arrive even when the site is closed. Works in Chrome, Edge, Firefox and Android; on iPhone only after "Add to Home Screen". Not available in private windows. |
| Razorpay payments | "Pay" on an invoice with `PAYMENT_GATEWAY=razorpay` | Real payments by UPI, card, net banking or wallet in Razorpay's own window; card details never reach this server. Every payment is verified by signature and re-checked with Razorpay (order, amount, status), and a webhook covers customers who close the page. Refunds are made in the Razorpay dashboard. |
| Refunds | Admin → Invoices → open a paid invoice → **Refund** | Refunds the whole payment (through Razorpay for a real payment; on record only for a test payment). A reason is required. The invoice becomes Refunded and cannot be paid again; the customer is notified. |
| Policy pages | `/privacy`, `/terms`, `/refunds`, `/contact`, linked from the landing, sign-in and register pages | Your business details come from the `BUSINESS_*` settings. The text is a starting point, not legal advice: read and adjust it. |
| Sign in with Google | "Sign in with Google" on Login and Register (needs `GOOGLE_CLIENT_ID`) | Signs in the account with the same email, or creates a customer account. Staff accounts are still created by an admin. "Forgot password?" works through it: sign in with Google, then choose a new password (allowed without the old one for 15 minutes after a Google sign-in), and it also clears a password lockout. |
| Staff accounts | Admin → **Staff** | Add drivers and mechanics to any center with a first password (or **Generate**), shown once to share with them. Mark staff on/off duty; automatic assignment skips off-duty staff. Staff change their password from the key icon. |
| Profile photos | Click your picture (top right) | Upload a photo or remove it; without one, your initials are shown. The server resizes it to a 256×256 JPEG, turns phone photos the right way up and removes location data (EXIF). Stored in the database, so it works on hosts without a disk. |
| Hindi / Kannada | Language menu (customer screens) | Navigation, home, booking, tracking, reminders, reviews. Staff screens stay in English. Translations need a native speaker's review. |

### The learned cost estimator, honestly

`train_cost_model` fits a ridge regression on the billed cost of approved repairs and prints a 5-fold
cross-validated comparison with the rule formula. With real repair history, that comparison is real
evidence. `python manage.py seed_repair_history --count 200` creates **synthetic** history only so the
pipeline can be demonstrated; a model trained on it only learns that made-up generator. The admin panel
and every estimate state the synthetic share, and synthetic jobs are hidden from analytics and booking lists.

## Deploying to production

**Step-by-step guide: [docs/DEPLOY.md](docs/DEPLOY.md). Checklist for after it is online:
[docs/AFTER_HOSTING.md](docs/AFTER_HOSTING.md).**

The product runs as one server at one address: with `DEBUG=False` the backend also serves the built
website (`client/dist`), so there is nothing separate to host for the frontend. A `Dockerfile` and a
Render blueprint (`render.yaml`) are included. With `DEBUG=False` the server refuses to start with
unsafe settings (demo login on, the mock payment gateway, a short `SECRET_KEY`, no `ALLOWED_HOSTS`,
or SQLite) and prints what to change.

Set these in `backend/.env` (or the server environment):

| Variable | Value |
|---|---|
| `DEBUG` | `False` |
| `SECRET_KEY` | A long random value: `python -c "import secrets; print(secrets.token_urlsafe(50))"`. The server refuses to start without one. |
| `ALLOWED_HOSTS` | Your domain(s), comma-separated |
| `DATABASE_URL` | `postgres://user:password@host:5432/dbname` (or `mysql://...`). Required: SQLite is refused in production unless `ALLOW_SQLITE_IN_PRODUCTION=True` (demos only). |
| `CORS_ALLOWED_ORIGINS` | Only if the website is hosted at a different address from the API; not needed with the one-server setup |
| `BUSINESS_*` | Your business name, legal name, address, email, phone and city for the policy pages |
| `FRONTEND_URL` | Public URL of the site (invoice QR codes link to `FRONTEND_URL/verify/...`) |
| `OTP_BYPASS` | `False` — **never** enable in production; it allows signing in to any existing account without a code |
| `PAYMENT_GATEWAY` | Leave empty: online payment is turned off and customers pay at the service center. `mock` is a test gateway only — it moves no real money. |
| `PAYMENT_GATEWAY=razorpay`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Real online payments. Use Razorpay's Test Mode keys first. Add the webhook `https://<API>/api/payments/razorpay/webhook/` (events `payment.captured`, `payment.failed`) in the Razorpay dashboard with the same secret. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CONTACT_EMAIL` | Browser alerts. Create the keys once with `python backend/manage.py generate_vapid_keys`; changing them later disconnects everyone who enabled alerts. The site must be served over HTTPS. |
| `GOOGLE_CLIENT_ID` | Optional: empty uses the project's own Google client, `off` hides Google sign-in. Add the production frontend URL to the OAuth client's Authorized JavaScript origins, and publish the Google app so people other than test users can sign in. |
| `USE_MYSQL`, `DB_*` | Older way to configure MySQL; `DATABASE_URL` is simpler |
| `MEDIA_ROOT` | Folder for uploaded photos; point it at a persistent disk on hosts that wipe the disk on deploy |

The frontend's `predev`/`prebuild` scripts copy the OCR engine and English language data from
`node_modules` into `client/public/ocr/`, so number plate reading never depends on a CDN.

## Payments

An invoice is created automatically when a booking is **Completed** (an admin can also regenerate it via `POST /api/bookings/<id>/generate-invoice/`). Invoices cannot be created before completion, and a paid invoice can no longer be changed.

Customers pay invoices from the Invoices page with UPI or card. Only a **mock gateway** exists today (`PAYMENT_GATEWAY=mock`, on by default in development): it records the payment and marks the invoice paid without charging anything, and the payment screen says so. Use `failure@mock` or card `4000 0000 0000 0002` to simulate a declined payment. Card numbers are validated (Luhn check) but only the last 4 digits are stored. A real gateway such as Razorpay plugs in at `backend/api/payment_service.py`.

## Pickup location (Book page)

Maps use **MapLibre GL** (open-source vector maps, the same kind of map engine delivery apps use) with the free **OpenFreeMap** "Liberty" style: no API key, no sign-up, no usage limit. Map data © OpenStreetMap contributors. To use a different style, set `VITE_MAP_STYLE_URL` in `client/.env`.

Customers pick their pickup point like in Swiggy or Zomato: the pin stays in the middle with a "Your car will be picked up here" bubble, and they move the map under it; when the map stops, the address under the pin is looked up. "Use current location" shows the phone's position as a pulsing blue dot. They can also search for a place or tap a preset area. Address search and "pin → address" lookups go through the backend (`/api/location/search/`, `/api/location/reverse/`), which follows OpenStreetMap's Nominatim usage policy: at most one request per second, an identifying User-Agent, and results cached for a day. The free search is less precise than Google for small lanes, so the address box stays editable for flat and house numbers. The distance to the chosen workshop is shown **by road** (OSRM, see "Live tracking"), or as a labelled straight-line estimate if routing is unavailable.

Optional: with `VITE_GOOGLE_MAPS_API_KEY` set in `client/.env` (Google Cloud billing account, Maps JavaScript + Places APIs), the Book page uses Google Maps instead.

## Live tracking

**Driver side.** On a job, the driver taps **Enable GPS**. The phone's GPS is watched continuously and a position is sent at most every 10 seconds; when the driver stands still, the last position is re-sent so the customer still sees "Live". The choice is remembered if the page is reloaded, and the screen is kept awake while sharing (on browsers that support it). Problems are shown instead of hidden: location permission blocked, no GPS signal, server unreachable, or a page that is not on `https://`/`localhost`.

Limits: this is a web page, not an installed app, so tracking stops when the driver locks the phone or switches apps (the **Simulate drive** button below avoids this for demos).

**Using a real phone as the driver.** Phone browsers only allow GPS on `https://` addresses (or `localhost`), so `http://192.168.x.x:5173` cannot share its location. Run the app in phone mode instead:
```bash
npm run dev:phone
```
It serves the frontend over `https://` on your Wi-Fi network and prints a **Network** address such as `https://192.168.1.20:5173`. Open that on the phone (same Wi-Fi as the laptop). The certificate is self-signed, so the phone warns once: tap **Advanced → Proceed**. Then sign in as the driver and tap **Enable GPS**. If your network blocks phone-to-laptop traffic (common on college Wi-Fi), use your phone's hotspot for both devices.

If GPS is still refused on Android Chrome, open `chrome://flags/#unsafely-treat-insecure-origin-as-secure` on the phone, add the address (for example `http://192.168.1.20:5173`), enable it and restart Chrome. For that plain-`http` setup, run `npm run dev:django` in one terminal and `npm run dev --prefix client -- --host` in another. This is for testing only.

**Demo: simulate the drive.** With `OTP_BYPASS=True` (demo mode), each job also has a **Simulate drive** button. It sends pretend GPS positions every 3 seconds along the road route (workshop → customer, or customer → workshop after pickup), taking about 2 minutes, so you can show the customer's Track page with the car moving without driving anywhere. Open the driver in one browser window and the customer's Track page in another (e.g. an Incognito window).

**Customer side.** The customer's Track page works like delivery-app order tracking: a home pin for the customer, a wrench pin for the workshop, and the driver as a car that glides smoothly to each new GPS position and turns the way it is driving. The route still ahead follows the actual roads, and a card shows "Driver arriving in X min" with the distance by road. The map follows the driver until the customer moves it; "Re-centre" turns following back on. It refreshes every 10 seconds.

Road routes come from **OSRM** (free, no API key) through the backend (`/api/location/route/`), cached for 10 minutes and limited to one request per second. A new route is fetched only when the driver leaves the current one. The public server (router.project-osrm.org) is a demo service with no uptime promise, and its times assume no traffic. If it is unreachable, the map shows a dashed straight line and the ETA is marked as a straight-line estimate. For heavier use, run your own OSRM server and set `ROUTING_URL` in `backend/.env`.

## About the cost estimator

Until a learned model is trained (see above), the repair cost estimator is **rule-based**: base service price × severity multiplier × fuel-type adjustment, plus labour at ₹500/hour, shown as a range of 85–125% of that figure. See `backend/api/ai_cost_service.py`. Every estimate reports which method produced it.

## Logo

The logo (a map pin with a front door: service at your doorstep) is drawn in `client/src/components/Logo.tsx`; the same drawing is the browser-tab icon `client/public/favicon.svg` and the phone home-screen icon `client/public/apple-touch-icon.png`. `docs/social-preview.png` is the picture GitHub shows when the repository link is shared: upload it under the repository's **Settings → General → Social preview**.

## Project layout

```
backend/            Django project (config/) and the api app: models, views, services, tests
client/             React frontend (unit tests next to the code as *.test.ts; browser tests in client/e2e/)
.github/workflows/  CI: runs all the tests on every pull request
research_paper/     Benchmark script used for the accompanying paper
```
