# Plan: Production Readiness & Render Deployment
- **Date:** 2026-09-27 19:53
- **Study:** [../study/2026-09-27-1953-render-deployment-prep.md](../study/2026-09-27-1953-render-deployment-prep.md)
- **Status:** in-progress

## Tasks (file by file)
- [ ] 1. **Dependencies:**
  - `requirements.txt`: pinned direct dependencies, grouped with comments: Django, Pillow, gunicorn, whitenoise, psycopg2-binary, dj-database-url, django-environ, cloudinary, django-cloudinary-storage.
  - `.python-version` → `3.14`.
  - → `build: add production dependencies`
- [ ] 2. **Environment-driven settings:**
  - `config/settings/base.py`: `environ.Env` + optional `.env`; `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS` from the environment with safe defaults; `DATABASES` via `dj_database_url.config(default=sqlite)`; WhiteNoise directly after `SecurityMiddleware`; default `STORAGES` (filesystem).
  - `dev.py`: environment with dev defaults.
  - `test.py`: SQLite unless `TEST_DATABASE_URL`.
  - `prod.py`: required `SECRET_KEY`/`ALLOWED_HOSTS`/`DATABASE_URL` (not SQLite)/`CLOUDINARY_URL`; `DEBUG` default False + warning; `RENDER_EXTERNAL_HOSTNAME`; `CSRF_TRUSTED_ORIGINS`; SSL-required database; `DISABLE_SERVER_SIDE_CURSORS`; WhiteNoise compressed manifest storage; Cloudinary media storage.
  - `.env.example` rewritten with the new variable names.
  - → `chore: configure production environment variables and dependencies`
- [ ] 3. **Build script:** `build.sh` (executable; errexit; forces prod settings; install; `collectstatic --no-input`; `migrate --no-input`; optional idempotent superuser from `DJANGO_SUPERUSER_*`). → `build: add render build script`
- [ ] 4. **Tests:** `config/tests/test_settings.py` (subprocess imports of dev/test/prod under controlled environments; required-variable failures; storage, middleware, and host assertions; `cloudinary_storage` isolated from dev/test; `build.sh` contract; `check --deploy`) + `config/tests/test_cloudinary_storage.py` (save an image through `MediaCloudinaryStorage` with the uploader mocked). → `test: cover production settings and cloudinary storage contract`
- [ ] 5. **Verify:**
  - Full suite green.
  - `check --deploy` with prod settings and dummy environment.
  - **Simulated Render build without Postgres** (none exists locally): run `collectstatic` with prod settings and a dummy environment to prove the WhiteNoise manifest build works. Then boot `gunicorn config.wsgi:application` with prod settings on a free port and check that `/accounts/login/` (no DB access) and an admin static file served by WhiteNoise both return 200.
  - Local `runserver` still works with no environment.
  - → fix commits as needed

## Blocked On
Nothing for the code. Deploying needs the Gardener's Neon, Cloudinary, and Render accounts (listed at Rendezvous).
