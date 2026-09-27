#!/bin/sh
# Render build script. Render dashboard → Build Command: sh build.sh
# (Start Command: gunicorn config.wsgi:application). See doc/wiki/deployment.md.
# Keep this POSIX sh: `sh build.sh` runs under dash on Render, so no bash-isms
# (e.g. `set -o pipefail` is rejected by older dash and would fail the build).
set -o errexit   # stop (and fail the deploy) on the first error

# manage.py defaults to dev settings; the build must configure production
# (Neon + Cloudinary + WhiteNoise), otherwise it would silently migrate a
# throwaway SQLite file on Render's ephemeral disk.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Optional: create the first admin (Render's free tier has no shell).
# Runs only when DJANGO_SUPERUSER_USERNAME is set, and only if that user doesn't exist yet.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  if python manage.py shell -c "import os, sys; from django.contrib.auth import get_user_model; sys.exit(0 if get_user_model().objects.filter(username=os.environ['DJANGO_SUPERUSER_USERNAME']).exists() else 1)"; then
    echo "Superuser '${DJANGO_SUPERUSER_USERNAME}' already exists; skipping."
  else
    python manage.py createsuperuser --no-input   # reads DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD
  fi
fi
