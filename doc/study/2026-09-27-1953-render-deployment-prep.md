# Study: Render Deployment Prep (Slice 6: Production Readiness)
- **Date:** 2026-09-27 19:53
- **Request:** Make the app production-ready for **Render.com's free tier** (ephemeral disk): **Neon Postgres** for data, **Cloudinary** for uploaded media, **WhiteNoise** for static files, **gunicorn** as the server, **django-environ** for configuration (`SECRET_KEY`, `DEBUG` defaulting to False, `ALLOWED_HOSTS`, `DATABASE_URL` from the environment), a `build.sh` (exit on error, install, `collectstatic --no-input`, `migrate`), and a clean `requirements.txt`. **Local development must keep working** (SQLite fallback when `DATABASE_URL` is missing).

## Intended Outcome
- The Gardener creates a Render web service from the GitHub repo, pastes the environment variables, sets **Build: `sh build.sh`** and **Start: `gunicorn config.wsgi:application`**, and the app runs. Data lives in Neon and images in Cloudinary, so both survive restarts and redeploys.
- On the Mac, `runserver` and `manage.py test` still work with **zero environment variables** (SQLite + local `media/`), exactly as today.

**Acceptance criteria**
- [ ] Production refuses to start without `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` (and it must not be SQLite), or `CLOUDINARY_URL`, and says clearly which one is missing.
- [ ] `DEBUG` comes from the environment and defaults to **False** in production.
- [ ] `WhiteNoiseMiddleware` sits directly after `SecurityMiddleware`. `collectstatic` produces compressed, hashed files in `STATIC_ROOT`.
- [ ] In production, uploaded images go to Cloudinary, and `post.image.url` / `ad.image.url` are Cloudinary URLs.
- [ ] `build.sh` fails the deploy on any error.
- [ ] `check --deploy` with production settings is clean, apart from the known HSTS-preload note.
- [ ] All existing tests pass locally, plus new tests covering the production configuration.

## Current State
**Settings are already split** (`config/settings/{base,dev,test,prod}.py`), not a single `settings.py`. `manage.py` defaults to `dev` (and `test` for the test command). `wsgi.py`/`asgi.py` default to **`prod`**. The request's "settings.py refactor" maps onto this structure: **shared environment handling in `base.py`, strict requirements in `prod.py`, and friendly defaults in `dev.py`/`test.py`.**

| Setting | Today | Where |
|---|---|---|
| `SECRET_KEY` | dev/test: hard-coded `django-insecure-…`. prod: `DJANGO_SECRET_KEY` env, required | dev.py, test.py, prod.py |
| `DEBUG` | dev True, test False, prod False (hard-coded) | each module |
| `ALLOWED_HOSTS` | dev localhost list. prod `DJANGO_ALLOWED_HOSTS` env, required | dev.py, prod.py |
| `DATABASES` | SQLite `db.sqlite3` everywhere | base.py |
| Static | `STATIC_URL`, `STATIC_ROOT = staticfiles/`. No production serving. | base.py |
| Media | `MEDIA_ROOT = media/`, served by `runserver` only when `DEBUG` | base.py, config/urls.py |
| Mail | prod: SMTP from `DJANGO_EMAIL_*` (nothing sends mail yet) | prod.py |
| HTTPS | prod: `SECURE_PROXY_SSL_HEADER`, SSL redirect, secure cookies, HSTS | prod.py |

**Environment variable names change** to the ones the Gardener specified: `DJANGO_SECRET_KEY` → **`SECRET_KEY`**, `DJANGO_ALLOWED_HOSTS` → **`ALLOWED_HOSTS`**. Nothing is deployed yet, so there's no migration cost. `.env.example` and the wiki will be updated.

## Verified facts (2026-09-27)
| Item | Finding |
|---|---|
| Latest versions | gunicorn **26.2.0** · whitenoise **6.12.0** · psycopg2-binary **2.9.13** (Python 3.14 macOS wheel ✓) · dj-database-url **3.1.2** · django-environ **0.14.0** · cloudinary **1.46.2** · django-cloudinary-storage **0.3.0** |
| Installs cleanly | All installed into `.venv` (Python 3.14). `pip check`: no broken requirements. |
| Render Python | Render's default for new Python services is **3.14.x** (changelog, Feb 2026), the same as local. A `.python-version` file pins it. |
| Local Postgres | **None** (no `postgres`/`psql`/Docker). The Postgres code path can't be tested locally without installing something. See Risks. |

### ⚠️ `django-cloudinary-storage` is unmaintained (last release Aug 2020, before Django 4.0)
I audited the installed source:
1. **`cloudinary_storage/app_settings.py` raises `ImproperlyConfigured` at import time** if no Cloudinary credentials are present. → It must be imported **only** in production. Dev and test must never reference it.
2. **Its `collectstatic` override reads `settings.STATICFILES_STORAGE`**, a setting **removed in Django 5.1**. Its README says to add `cloudinary_storage` to `INSTALLED_APPS` before `django.contrib.staticfiles`. **Doing that would crash `collectstatic` on Django 6.1, and therefore the Render build.** → **Do not add it to `INSTALLED_APPS`.** The media backend (`MediaCloudinaryStorage`) is a plain `Storage` subclass that doesn't need app registration.
3. `MediaCloudinaryStorage` implements `_save`, `_open`, `delete`, `exists`, `size`, `url`, `listdir`, and `get_available_name(name, max_length=None)`. These are the methods Django 6.1's `Storage.save()` path uses. **A contract test** will prove it works with our `ImageField`s: it saves a `Post` image through the backend with the Cloudinary upload mocked, and checks the stored name and the `https://res.cloudinary.com/...` URL.

**Alternatives considered:** calling `cloudinary` directly through a small custom `Storage` class (about 40 lines), or `django-storages` with S3 or R2. **Decision: use the package the Gardener chose, confined as above and protected by the contract test.** If a future Django breaks it, the fallback is a tiny in-repo `Storage` class, and no model changes would be needed either way.

## Design

### Environment handling (`django-environ`)
```python
# base.py
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")      # optional local file (gitignored); real env vars win
```
- **`base.py`** (shared, safe defaults):
  - `DEBUG = env.bool("DEBUG", default=False)`
  - `SECRET_KEY = env.str("SECRET_KEY", default="")`
  - `ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])`
  - `DATABASES = {"default": dj_database_url.config(default="sqlite:///…/db.sqlite3", conn_max_age=600, conn_health_checks=True)}` → **SQLite when `DATABASE_URL` is missing.**
- **`dev.py`:** keeps working with **no** environment. `DEBUG = env.bool("DEBUG", default=True)`, `SECRET_KEY = env.str("SECRET_KEY", default="django-insecure-dev-only…")`, `ALLOWED_HOSTS` default localhost. The dev fallback key isn't a secret: it only ever signs local sessions.
- **`test.py`:** **always SQLite** unless the opt-in **`TEST_DATABASE_URL`** is set. This way a `DATABASE_URL` in a local `.env` can never make the test suite create test databases in the Neon production project by accident. Fixed test key, fast hasher (unchanged).
- **`prod.py`** (strict):
  - `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `CLOUDINARY_URL` are **required**. A missing one raises `ImproperlyConfigured("Environment variable X is required in production.")`.
  - `DATABASE_URL` must not be SQLite (the Render disk is ephemeral).
  - `DEBUG = env.bool("DEBUG", default=False)`. **A warning is printed if DEBUG is True in production** (debug pages leak settings), but it isn't blocked, because turning DEBUG on briefly can help diagnose a failed first deploy.
  - `ALLOWED_HOSTS` also gets Render's automatic **`RENDER_EXTERNAL_HOSTNAME`**, so the `*.onrender.com` host works even if the Gardener forgets it. `CSRF_TRUSTED_ORIGINS` is derived from the hosts as `https://<host>`.
  - The database uses `ssl_require=True` (Neon requires TLS) and **`DISABLE_SERVER_SIDE_CURSORS = True`**, which is required for Neon's **pooled** (PgBouncer, transaction-mode) connection string. The code never uses `.iterator()` anyway.

### Static files (WhiteNoise)
- `"whitenoise.middleware.WhiteNoiseMiddleware"` goes **directly after** `SecurityMiddleware`, in `base.py`. It's harmless in development.
- `STATIC_ROOT = BASE_DIR / "staticfiles"` (already set, and already gitignored).
- `STORAGES["staticfiles"]`:
  - prod → `whitenoise.storage.CompressedManifestStaticFilesStorage` (gzip/brotli + hashed, cache-forever names)
  - dev/test → Django's default `StaticFilesStorage` (no manifest needed, so tests and `runserver` don't require `collectstatic`)
- What gets collected: only the **Django admin's** static files. The app's own CSS comes from the Tailwind CDN, and templates don't use `{% static %}`.

### Media (Cloudinary)
- `STORAGES["default"]`:
  - prod → `cloudinary_storage.storage.MediaCloudinaryStorage`
  - dev/test → `FileSystemStorage` (`media/`, unchanged)
- `CLOUDINARY_URL` (`cloudinary://<api_key>:<api_secret>@<cloud_name>`) is read by the Cloudinary SDK and by `cloudinary_storage` straight from the environment. `prod.py` checks it exists **before** the storage module is imported, so a missing value produces our clear message rather than the library's.
- Uploads keep their `upload_to` folders (`posts/%Y/%m/`, `ads/%Y/%m/`) as Cloudinary folders. The 5 MB limit and Pillow validation run **before** upload, unchanged.
- `config/urls.py` media serving stays `DEBUG`-only. In production, image URLs point at `res.cloudinary.com`.

### Server
- **Start command:** `gunicorn config.wsgi:application`. The project package is **`config`**, not `projectname`. `wsgi.py` already defaults to `config.settings.prod`.
- gunicorn automatically binds `0.0.0.0:$PORT` when Render sets `PORT`. Workers come from `WEB_CONCURRENCY` (recommend **2** on the 512 MB free instance).

### `build.sh`
```bash
#!/usr/bin/env bash
set -o errexit                                   # exit on error
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
# optional: create the first admin (Render free has no shell), idempotent
```
- **Why export `DJANGO_SETTINGS_MODULE`:** `manage.py` defaults to **dev** settings. Without this, the build would collect and migrate using dev settings (SQLite on the ephemeral disk) and would **silently not touch Neon**.
- **Optional first-admin step (an addition, flagged):** Render's free tier offers no interactive shell (to be confirmed in the dashboard), so there's no way to run `createsuperuser`. If `DJANGO_SUPERUSER_USERNAME`, `…_EMAIL`, and `…_PASSWORD` are set, the build creates that superuser **only if it doesn't exist yet** (safe on every deploy). If the variables are unset, it does nothing.
- `.python-version` → `3.14` so Render and local development match.

### `requirements.txt`
Direct dependencies only, **pinned exactly**, grouped with comments (runtime · production server · data · media). Transitive dependencies (e.g. `requests`, `certifi`, `urllib3` via Cloudinary) are resolved by pip. Full lock files or hashes would be overkill for a hobby deploy; `pip check` guards consistency.

## Postgres compatibility of the existing code
Everything used is standard SQL that Django supports on Postgres:
- constraints: `Lower(email)` unique, CHECK constraints, composite unique
- window functions (sliced prefetch)
- `COUNT(DISTINCT)`, `EXISTS`, `bulk_create` (returns IDs on Postgres), `in_bulk`, `iexact`
- migrations: generated by Django, nothing SQLite-specific

**Risk:** this is untested until a real Postgres exists. **Mitigation:** once the Gardener has created the Neon project, run the **full suite against Neon once** with the opt-in `TEST_DATABASE_URL`. It creates and drops a temporary `test_…` database, and a small SSL test settings tweak keeps it compatible. The runbook will include the exact command.

## Tests to add (production configuration contract)
Settings modules are tested by **importing them in a subprocess** with controlled environments, since prod settings must fail fast at import.
- prod import **fails** when each required variable is missing, and when `DATABASE_URL` is SQLite.
- prod import **succeeds** with all variables set, and verifies: `DEBUG` False by default, WhiteNoise position, `STORAGES` backends, `RENDER_EXTERNAL_HOSTNAME` added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, `DISABLE_SERVER_SIDE_CURSORS`, and SSL required.
- dev and test settings import with **no environment** and use SQLite and FileSystemStorage. `cloudinary_storage` **is not imported** in dev or test.
- **Cloudinary contract:** save a `Post` with an image through `MediaCloudinaryStorage` (the uploader is mocked, so there are no network calls) and check the stored name and URL.
- `build.sh` exists, is executable, uses `set -o errexit`, and forces prod settings.
- `manage.py check --deploy --settings=config.settings.prod` with dummy values passes, apart from the HSTS-preload warning.

## Exogenous Inputs
| Input | Why | Status | Owner |
|---|---|---|---|
| **Neon** project + database, **pooled** connection string | `DATABASE_URL` | Needed at deploy | Gardener |
| **Cloudinary** account → `CLOUDINARY_URL` (API Environment variable on the dashboard) | Media storage | Needed at deploy | Gardener |
| **Render** web service connected to `ShmuelNg1212/WhatsUp` | Hosting | Needed at deploy | Gardener |
| A generated `SECRET_KEY` | Signing | Gardener generates (command provided) | Gardener |
| Render free-tier shell availability | Superuser creation approach | Assumed unavailable. The build-time superuser step covers it either way. | Gardener to observe |

Secrets are **never pasted in chat** and never committed. They go into the Render dashboard (and, optionally, a local gitignored `.env`).

## Risks & Open Questions
1. **Unmaintained `django-cloudinary-storage`.** Mitigated by keeping it out of `INSTALLED_APPS`, importing it in prod only, and the contract test. The fallback is a small in-repo storage class.
2. **Postgres is untested locally.** Mitigated by a one-time full-suite run against Neon (documented).
3. **Existing local data isn't migrated.** Production starts empty (fresh Neon database). That's intentional: demo accounts with known passwords must not go live.
4. **Free-tier behavior:** Render sleeps after about 15 minutes idle (30–60 s cold start). Neon's free compute also suspends when idle, which adds about a second to the first query. This is expected.
5. **Media deletions:** deleting a post or ad doesn't delete its Cloudinary asset (existing known gap).
6. **Impression writes** hit Neon on every feed view, which is fine at hobby scale.
