# One image for the whole product: the built website and the API, served together at one address.
#   docker build -t doorstep .
#   docker run --env-file backend/.env -p 8000:8000 doorstep
# See docs/DEPLOY.md for the settings a live server needs.

# --- 1. Build the website --------------------------------------------------------------------
FROM node:22-slim AS website
WORKDIR /src/client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# --- 2. The server ---------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=website /src/client/dist /app/client/dist

# Not root, and able to write uploads and collected static files
RUN useradd --create-home --uid 10001 app && mkdir -p /app/backend/media /app/backend/staticfiles && chown -R app:app /app
USER app

EXPOSE 8000
# Update the database, gather Django's static files, then start the web server.
# PORT is set by most hosts; WEB_CONCURRENCY is the number of worker processes.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60 --access-logfile -"]
