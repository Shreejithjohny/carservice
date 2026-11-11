# Putting DoorStep online

The whole product runs as **one server at one address**: it serves the website and the API
together. You need a host that can run a Docker container (or Python) and a PostgreSQL database.

What was tested: the Docker image builds and runs, and the full test suites pass on PostgreSQL 16.
What was not: any particular hosting company. `render.yaml` is written from Render's documentation
and has not been run there.

## 1. What the server needs

Set these as environment variables on the host (locally they live in `backend/.env`).
With `DEBUG=False` the server **refuses to start** if a setting would be unsafe, and lists every
problem at once.

| Setting | Value |
|---|---|
| `DEBUG` | `False` |
| `SECRET_KEY` | A long random value: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | Your domain(s), comma-separated, e.g. `app.example.com` (Render fills this in by itself) |
| `DATABASE_URL` | `postgres://user:password@host:5432/dbname` (the host gives you this) |
| `FRONTEND_URL` | Your public address, e.g. `https://app.example.com` (used in invoice QR codes) |
| `OTP_BYPASS` | `False` |
| `PAYMENT_GATEWAY` | empty (pay at the service center) or `razorpay` |
| `BUSINESS_NAME`, `BUSINESS_LEGAL_NAME`, `BUSINESS_ADDRESS`, `BUSINESS_EMAIL`, `BUSINESS_PHONE`, `BUSINESS_CITY`, `BUSINESS_GSTIN` (optional) | Shown on `/privacy`, `/terms`, `/refunds` and `/contact` |

Optional: `GOOGLE_CLIENT_ID`, `RAZORPAY_*`, `VAPID_*` (see `docs/AFTER_HOSTING.md`),
`MEDIA_ROOT` (where uploaded photos are stored), `WEB_CONCURRENCY` (worker processes, default 2).

## 2. Deploy

### Option A: Render (blueprint included)
1. Push this repository to GitHub.
2. On render.com: **New > Blueprint**, choose the repository. It reads `render.yaml`, creates the
   web server and a PostgreSQL database, and connects them.
3. Fill in the values it asks for (`FRONTEND_URL`, the `BUSINESS_*` details).
4. Open the address Render gives you.

Check Render's current plans first: free web servers sleep when idle, free databases expire, and
the free plan has no persistent disk (see "Uploaded photos" below).

### Option B: any host that runs Docker (Railway, Fly.io, a VPS, ...)
```bash
docker build -t doorstep .
```
```bash
docker run --env-file backend/.env -p 8000:8000 doorstep
```
On start the container updates the database (`migrate`), collects static files and starts the web
server on `$PORT` (default 8000). Put HTTPS in front of it (most hosts do this for you).

### Option C: without Docker
```bash
pip install -r backend/requirements.txt
```
```bash
npm ci --prefix client && npm run build --prefix client
```
```bash
cd backend && python manage.py migrate && python manage.py collectstatic --noinput
```
```bash
cd backend && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 2
```

## 3. First start
Create your own admin (do not use the demo accounts on a live site):
```bash
python manage.py createsuperuser
```
Add your service packages and service centers in the Django admin site at `/django-admin/`
(the website's own admin area is at `/admin`). To load the sample packages and centers instead:
```bash
python manage.py seed_vehicle_catalog && python manage.py seed_service_data
```
Do **not** run `seed_demo_accounts` on a live site: it creates demo logins.

## 4. Moving existing data from SQLite to PostgreSQL
Only needed if you already have real data in `backend/db.sqlite3`.

1. Export from SQLite (with no `DATABASE_URL` set):
   ```bash
   python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e sessions -e admin.logentry -o data.json
   ```
2. Point `DATABASE_URL` at the new, empty PostgreSQL database, then:
   ```bash
   python manage.py migrate
   ```
   ```bash
   python manage.py loaddata data.json
   ```
3. Sign in and check a few bookings and invoices. Keep `db.sqlite3` until you are sure.

Uploaded photos are files, not database rows: copy the `backend/media/` folder to the new server too.

## 5. Uploaded photos (important)
Car condition photos and repair evidence are stored as files in `MEDIA_ROOT`
(default `backend/media/`). Many hosts wipe the disk on every deploy. Either attach a persistent
disk and set `MEDIA_ROOT` to it, or accept that photos are lost on redeploy.
Uploaded files are served at `/media/...` to anyone who has the exact link.

## 6. After it is online
Follow `docs/AFTER_HOSTING.md`.

## Troubleshooting
| What you see | Cause |
|---|---|
| The server exits with "Unsafe production settings" | Read the list it prints; each line says what to change. |
| "Bad Request (400)" on every page | Your domain is missing from `ALLOWED_HOSTS`. |
| Endless redirect | Your host does not send `X-Forwarded-Proto`. Set `SECURE_SSL_REDIRECT=False` and let the host force HTTPS. |
| The website shows but `/api/...` fails | Look at the server log; usually the database address is wrong. |
| Demo buttons on the sign-in page | `OTP_BYPASS` is on. With `DEBUG=False` the server will not even start that way. |
