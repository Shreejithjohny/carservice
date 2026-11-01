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

Anyone who signs up gets a **Customer** account. Drivers and mechanics are added by an admin or a manager on the **Staff** page; the seed script also creates one demo account per role.

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
| Backend (Django) | API rules: bookings, slots, OTPs, passwords, payments, invoices, auto-assignment, ... | `python backend/manage.py test api` (should end with "OK") |
| Frontend unit (Vitest) | Small helpers: distances, road-route maths, ETAs, map arrow direction, simulated-drive spacing, sign-in routes | `npm test --prefix client` (with coverage: `npm run test:coverage --prefix client`) |
| Browser (Playwright) | The real app in Chrome: sign in, book a pickup on the map, the manager confirms and a driver is auto-assigned, the driver shares GPS or simulates the drive, the customer tracks it, a manager adds staff | `npm run test:e2e --prefix client` |

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
| Create your own admin login for the Django admin site (http://127.0.0.1:8000/admin/) | `python backend/manage.py createsuperuser` |
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
| Manager | manager@smartdoorstep.com |
| Driver | driver@smartdoorstep.com |
| Mechanic | mechanic@smartdoorstep.com |
| Customer | customer@smartdoorstep.com |

To also sign in to the demo accounts with email + password, set `DEMO_ACCOUNT_PASSWORD` in `backend/.env` to a password of your choice **before** running `npm run seed`. The seed gives each demo account that password, but only if the account has none yet, so a password that was changed is never reset. The password lives only in your `.env`, never in the code.

The sign-in page has a tab per role, each with its own address, so staff can bookmark theirs: `/login/customer`, `/login/driver`, `/login/mechanic`, `/login/manager`, `/login/admin`. Signing in on the wrong tab (for example a driver on the Customer tab) is refused, with a link to the right tab.

With `OTP_BYPASS=True` (set in `.env.example`) each tab shows a "Try the demo … account" button. With it off, people sign in with their password or a one-time code. Without SMS/email configured, one-time codes are printed in the backend console (development only).

## Features at a glance

| Feature | Where | Notes |
|---|---|---|
| Pickup time slots | Book page; `GET /api/service-centers/<id>/slots/?date=` | Four windows a day, `slot_capacity` per center (Django admin). Up to 30 days ahead. |
| Return delivery | Driver: *Start Return Delivery* → *Hand Back Car*; customer sees the delivery OTP on Track | The delivery OTP completes the booking and issues the invoice. Managers can still mark *Collected at Center*. |
| Condition photos & odometer | Driver at pickup and delivery; customer's Track page | Before/after per side, and km driven while the center had the car. |
| Number plate check | Driver at pickup | OCR runs in the browser (tesseract.js); the backend matches it against the registration. Works on clear photos; glare, dirt and steep angles reduce accuracy. |
| Service reminders | Customer home page; `python manage.py send_service_reminders` | Due 6 months or 10,000 km after the last service. Run the command once a day (cron / Windows Task Scheduler). |
| Automatic staff assignment | Manager clicks **Confirm**; **Assign Staff** shows the ranked list | Driver = lowest *distance to the customer (km) + 3 km × pickups already that day*, among available drivers of that center who are free in the booking's time slot. Position = latest GPS if under 2 hours old, else the driver's service center. Mechanic = fewest open jobs. The manager can always pick someone else. Code: `backend/api/dispatch_service.py` |
| Ratings & reviews | Customer: Track or History after completion | Centers show the real average or "new, no reviews yet". |
| PDF invoice + QR | Invoices → *Download PDF*; QR opens `/verify/<code>` | Code is signed with `SECRET_KEY`. Titled INVOICE, not TAX INVOICE: the app stores no GSTIN. |
| Analytics | Manager and admin → Analytics | Revenue, bookings, turnaround, top repairs, approval rate, ratings. |
| Learned cost estimator | Admin overview → *Repair cost model*; `python manage.py train_cost_model` | Used once 30+ completed, approved repairs exist; otherwise the rule formula. See below. |
| Email + password sign-in | Login, Register, Forgot password; key icon in the header to change password | Passwords are hashed by Django and must pass its strength rules. 5 wrong passwords lock the account for 15 minutes. "Forgot password" sends a 6-digit code by email/SMS. Sign-in with a one-time code still works. |
| Staff accounts | Admin or manager → **Staff** | Add drivers and mechanics (admins: any center; managers: their own) with a first password (or **Generate**), shown once to share with them. Mark staff on/off duty; automatic assignment skips off-duty staff. Staff change their password from the key icon. |
| Profile photos | Click your picture (top right) | Upload a photo or remove it; without one, your initials are shown. The server resizes it to a 256×256 JPEG, turns phone photos the right way up and removes location data (EXIF). Stored in the database, so it works on hosts without a disk. |
| Hindi / Kannada | Language menu (customer screens) | Navigation, home, booking, tracking, reminders, reviews. Staff screens stay in English. Translations need a native speaker's review. |

### The learned cost estimator, honestly

`train_cost_model` fits a ridge regression on the billed cost of approved repairs and prints a 5-fold
cross-validated comparison with the rule formula. With real repair history, that comparison is real
evidence. `python manage.py seed_repair_history --count 200` creates **synthetic** history only so the
pipeline can be demonstrated; a model trained on it only learns that made-up generator. The admin panel
and every estimate state the synthetic share, and synthetic jobs are hidden from analytics and booking lists.

## Host it on Vercel (free)

The whole app runs as **one Vercel project**: the React site, plus the Django API as a Python function under `/api` (`vercel.json`, `api/index.py`). Vercel keeps no files, so the data lives in a free **Neon** Postgres database. Total cost: ₹0 on both free plans.

**1. Create the database (Neon)**
1. Sign up at **neon.tech** (Continue with GitHub).
2. **Create project**: any name, region **Asia Pacific (Singapore)** (closest to India).
3. On the project dashboard, click **Connect**, tick **Connection pooling**, and copy the connection string. It looks like `postgresql://user:password@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`. Keep it secret.

**2. Fill the database from your laptop (once)**
In `backend/.env`, add (temporarily):
```
DATABASE_URL=<the Neon connection string>
DEMO_ACCOUNT_PASSWORD=<a password for the demo accounts>
```
Then, from the project folder:
```bash
pip install -r backend/requirements.txt
npm run migrate:django
npm run seed
```
Afterwards **delete the `DATABASE_URL` line** from `backend/.env`, so your laptop goes back to its own SQLite database.

**3. Create the Vercel project**
1. Sign up at **vercel.com** (Continue with GitHub) and allow it to see the `carservice` repository.
2. **Add New → Project → Import** `carservice`. Leave **Framework Preset: Other** and **Root Directory: ./**; build settings come from `vercel.json`.
3. Under **Environment Variables**, add:

| Name | Value |
|---|---|
| `DATABASE_URL` | The Neon connection string |
| `SECRET_KEY` | A long random value: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `False` |
| `DEMO_TOOLS` | `True` to show **Simulate drive** for demos (optional) |

4. Click **Deploy**. After a few minutes you get an address like `https://carservice-xyz.vercel.app`. Every push to `main` deploys again automatically.

**4. Try it**: open the address and sign in on each tab with the demo emails (see "Demo accounts") and your `DEMO_ACCOUNT_PASSWORD`.

**Do not set `OTP_BYPASS=True` on Vercel.** Its demo buttons sign anyone in to existing accounts, admin included, without a password. `DEMO_TOOLS` gives you Simulate drive without that.

**Limits of the free hosting**
- **Photos taken by drivers and mechanics** (condition photos, repair evidence) are not kept: Vercel's disk is wiped between requests. Profile photos are kept (they are stored in the database). Keeping the others needs file storage such as Vercel Blob or Cloudinary.
- **One-time codes by SMS/email** need Twilio or email settings in the Vercel environment variables; without them, sign in with passwords.
- **First request after a quiet period** takes a few seconds while Vercel and Neon wake up.
- **The Django admin** at `/admin/` is not styled there; use the app's own Staff and Car Catalog pages.
- **Booking and status changes** made by the API are stored in Neon, so they survive redeploys.

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
| `DATABASE_URL` | Postgres connection URL (e.g. Neon); takes priority over MySQL and SQLite |
| `DEMO_TOOLS` | `True` shows the driver's **Simulate drive** without enabling `OTP_BYPASS` |
| `USE_MYSQL`, `DB_*` | Optional MySQL connection |

The frontend's `predev`/`prebuild` scripts copy the OCR engine and English language data from
`node_modules` into `client/public/ocr/`, so number plate reading never depends on a CDN.

## Payments

An invoice is created automatically when the service center manager marks a booking **Completed** (an admin or that center's manager can also regenerate it via `POST /api/bookings/<id>/generate-invoice/`). Invoices cannot be created before completion, and a paid invoice can no longer be changed.

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
