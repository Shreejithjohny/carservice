# One image for the whole product: the built website and the API, served together at one address.
#   docker build -t doorstep .
#   docker run --env-file backend/.env -p 8000:8000 doorstep
# See docs/DEPLOY.md for the settings a live server needs.

# --- 1. Build the website --------------------------------------------------------------------
FROM node:22-slim AS website
WORKDIR /src/client
COPY client/package.json client/package-lock.json ./
# Exact versions from package-lock.json; packages' own install scripts are not run
RUN npm ci --ignore-scripts
COPY client/ ./
RUN npm run build

# --- 2. The server ---------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
# Exact, hash-checked versions (requirements-lock.txt), and only pre-built packages: nothing from
# the internet gets to run a setup script during the install
COPY backend/requirements-lock.txt ./
RUN pip install --require-hashes --only-binary :all: -r requirements-lock.txt
COPY backend/ ./
COPY --from=website /src/client/dist /app/client/dist

# Not root, and able to write uploads and collected static files
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/backend/media /app/backend/staticfiles \
    && chown -R app:app /app
USER app

EXPOSE 8000
# Updates the database, gathers static files, then starts the web server (see docker-start.sh)
CMD ["./docker-start.sh"]
