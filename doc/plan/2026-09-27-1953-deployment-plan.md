# Plan: Production Readiness & Render Deployment
- **Date:** 2026-09-27 19:53
- **Study:** [../study/2026-09-27-1953-render-deployment-prep.md](../study/2026-09-27-1953-render-deployment-prep.md)
- **Status:** done

## Tasks (file by file)
- [x] 1. **Dependencies:**
  - `requirements.txt`: pinned direct dependencies, grouped with comments: Django, Pillow, gunicorn, whitenoise, psycopg2-binary, dj-database-url, django-environ, cloudinary, django-cloudinary-storage.
  - `.python-version` → `3.14`.
  - → `build: add production dependencies`
- [x] 2. **Environment-driven settings:**
  - `config/settings/base.py`: `environ.Env` + optional `.env`; `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS` from the environment with safe defaults; `DATABASES` via `dj_database_url.config(default=sqlite)`; WhiteNoise directly after `SecurityMiddleware`; default `STORAGES` (filesystem).
  - `dev.py`: environment with dev defaults.
  - `test.py`: SQLite unless `TEST_DATABASE_URL`.
  - `prod.py`: required `SECRET_KEY`/`ALLOWED_HOSTS`/`DATABASE_URL` (not SQLite)/`CLOUDINARY_URL`; `DEBUG` default False + warning; `RENDER_EXTERNAL_HOSTNAME`; `CSRF_TRUSTED_ORIGINS`; SSL-required database; `DISABLE_SERVER_SIDE_CURSORS`; WhiteNoise compressed manifest storage; Cloudinary media storage.
  - `.env.example` rewritten with the new variable names.
  - → `chore: configure production environment variables and dependencies`
- [x] 3. **Build script:** `build.sh` (executable; errexit; forces prod settings; install; `collectstatic --no-input`; `migrate --no-input`; optional idempotent superuser from `DJANGO_SUPERUSER_*`). → `build: add render build script`
- [x] 4. **Tests:** `config/tests/test_settings.py` (subprocess imports of dev/test/prod under controlled environments; required-variable failures; storage, middleware, and host assertions; `cloudinary_storage` isolated from dev/test; `build.sh` contract; `check --deploy`) + `config/tests/test_cloudinary_storage.py` (save an image through `MediaCloudinaryStorage` with the uploader mocked). → `test: cover production settings and cloudinary storage contract`
- [x] 5. **Verify:**
  - Full suite green.
  - `check --deploy` with prod settings and dummy environment.
  - **Simulated Render build without Postgres** (none exists locally): run `collectstatic` with prod settings and a dummy environment to prove the WhiteNoise manifest build works. Then boot `gunicorn config.wsgi:application` with prod settings on a free port and check that `/accounts/login/` (no DB access) and an admin static file served by WhiteNoise both return 200.
  - Local `runserver` still works with no environment.
  - → fix commits as needed

## Verification results
- **309/309 tests pass** (288 → 309). The 21 new tests cover the production-settings contract, local-settings isolation, `build.sh`, requirements, and the Cloudinary storage contract (uploader mocked).
- Mutation checks: adding `cloudinary_storage` to `INSTALLED_APPS` → 3 failures (dev and test can no longer start without credentials, as the study predicted). Moving WhiteNoise away from `SecurityMiddleware` → caught.
- `check --deploy` with prod settings: only the intentional HSTS-preload note.
- **Simulated Render build** in a scratch clone, with prod settings and a dummy environment:
  - `collectstatic`: 130 files, 390 post-processed, manifest + 260 gzip variants.
  - gunicorn booted 2 workers on `0.0.0.0:$PORT`. HTTP → 301 to HTTPS. HTTPS pages 200. Admin CSS served by WhiteNoise with gzip and `max-age=315360000, immutable`. HSTS header present. Unknown host → 400.
  - (zsh doesn't word-split variables; the first probe attempts were re-run under bash.)
- **Caught before handover:** Render runs `sh build.sh` under dash, which older versions reject on `set -o pipefail`. With errexit that would have failed the first deploy. `build.sh` is now POSIX `sh`, tested with `sh -n`, `bash --posix -n`, and a no-bash-isms check → `fix(build): keep build.sh POSIX so Render's sh (dash) can run it`.
- Local `runserver` still works with **no** environment (SQLite, local media).
- **Not yet verified:** `migrate` on real Postgres (no local Postgres). This happens on the first Render deploy against Neon, or beforehand via `TEST_DATABASE_URL` (see Rendezvous).

## Blocked On
Nothing for the code. Deploying needs the Gardener's Neon, Cloudinary, and Render accounts (listed at Rendezvous).
