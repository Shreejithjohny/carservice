#!/bin/sh
# Starts the DoorStep container: update the database, gather Django's static files, then run the
# web server. PORT is set by most hosts; WEB_CONCURRENCY is the number of worker processes.
set -e

MEDIA_DIR="${MEDIA_ROOT:-/app/backend/media}"

# A host's persistent disk (for uploaded photos) is usually mounted owned by root, which the app
# user cannot write to. The container therefore starts as root only to take ownership of the upload
# folder, then switches to the unprivileged "app" user before anything else runs.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$MEDIA_DIR"
  chown app:app "$MEDIA_DIR"
  export HOME=/home/app
  exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

if [ ! -w "$MEDIA_DIR" ]; then
  echo "Uploads folder $MEDIA_DIR is not writable by $(id -un). Check MEDIA_ROOT and the disk." >&2
  exit 1
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60 \
  --access-logfile -
