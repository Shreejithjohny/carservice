#!/bin/sh
# Starts the DoorStep container: update the database, gather Django's static files, then run the
# web server. PORT is set by most hosts; WEB_CONCURRENCY is the number of worker processes.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60 \
  --access-logfile -
