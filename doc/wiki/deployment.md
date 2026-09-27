# Deployment

WhatsUp runs on **Render.com** (free web service), with data in **Neon Postgres** and uploaded images on **Cloudinary**. Render's disk is **ephemeral** (it's wiped on every deploy and restart), so **nothing persistent lives on the app server.**

Background and design decisions: [Slice 6 study](../study/2026-09-27-1953-render-deployment-prep.md).

---

## 1. Production architecture

```
                         ┌──────────────── Render (free web service) ───────────────┐
 Browser ── HTTPS ──▶ Render proxy (TLS) ──▶ gunicorn ──▶ Django (config.settings.prod)
                         │                     │  WhiteNoise: /static/  (admin CSS/JS,
                         │                     │  compressed + hashed, from STATIC_ROOT)
                         └─────────────────────┼──────────────────────────────────────┘
                                               │
                        DATABASE_URL (TLS) ────┼──────▶ Neon Postgres (pooled endpoint)
                        CLOUDINARY_URL ────────┴──────▶ Cloudinary (post and ad images)
 Browser ◀── images load directly from https://res.cloudinary.com/…
 Browser ◀── Tailwind CSS + Inter font from public CDNs (jsDelivr, Google Fonts)
```

### Infrastructure stack
| Layer | Service / tool | Configured in |
|---|---|---|
| Hosting | **Render** web service, Free plan, Python runtime (**3.14**, pinned by `.python-version`) | Render dashboard |
| Web server | **gunicorn 26.2** (binds `0.0.0.0:$PORT`, workers from `WEB_CONCURRENCY`) | Start command |
| Static files | **WhiteNoise 6.12**, `CompressedManifestStaticFilesStorage` | `config/settings/base.py` (middleware), `prod.py` (storage) |
| Database | **Neon** serverless Postgres via **dj-database-url 3.1** + **psycopg2-binary 2.9** | `DATABASE_URL` → `prod.py` |
| Media | **Cloudinary** via **cloudinary 1.46** + **django-cloudinary-storage 0.3** | `CLOUDINARY_URL` → `prod.py` |
| Configuration | **django-environ 0.14** (environment variables, optional `.env`) | `config/settings/*.py` |
| Source | GitHub `ShmuelNg1212/WhatsUp`, branch `main` | Render Auto-Deploy |

### Settings modules
| Module | Used by | Database | Media | Needs environment? |
|---|---|---|---|---|
| `config.settings.dev` | `manage.py` (default) | `DATABASE_URL` or **SQLite** `db.sqlite3` | local `media/` | No |
| `config.settings.test` | `manage.py test` (automatic) | **Always SQLite** (opt-in `TEST_DATABASE_URL`) | local (temp dirs) | No |
| `config.settings.prod` | `wsgi.py`/`asgi.py` (default), `build.sh` (default) | `DATABASE_URL` (**must be Postgres**) | Cloudinary | **Yes**: fails fast, naming the missing variable |

## 2. Render configuration

| Field | Value |
|---|---|
| Runtime | Python 3 |
| Branch | `main` (Auto-Deploy on) |
| **Build Command** | `sh build.sh` |
| **Start Command** | `gunicorn config.wsgi:application` |
| Instance type | Free |

**`build.sh`** (POSIX `sh`, since Render runs it with dash) does the following, and any failing step fails the deploy while the previous version stays live:
1. `set -o errexit`
2. `DJANGO_SETTINGS_MODULE` defaults to `config.settings.prod`. Without this, `manage.py` would use dev settings and migrate a throwaway SQLite file.
3. `pip install -r requirements.txt`
4. `python manage.py collectstatic --no-input`
5. `python manage.py migrate --no-input`
6. If `DJANGO_SUPERUSER_USERNAME` is set and that user doesn't exist: `createsuperuser --no-input`. This is idempotent and never changes an existing user.

## 3. Environment variables

Set these in **Render → service → Environment.** Secrets never go into git or chat.

| Variable | Required | Value / source |
|---|---|---|
| `SECRET_KEY` | ✅ | Random string. `.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key(), end='')" \| pbcopy` |
| `ALLOWED_HOSTS` | ✅* | Comma-separated hostnames, e.g. `whatsup-xxxx.onrender.com`. *Render's `RENDER_EXTERNAL_HOSTNAME` is added automatically, so this can be omitted if Render sets that. |
| `DATABASE_URL` | ✅ | Neon → **Connect** → **pooled** connection string (`…-pooler…/neondb?sslmode=require`) |
| `CLOUDINARY_URL` | ✅ | Cloudinary → API Keys → **API environment variable** (`cloudinary://key:secret@cloud`) |
| `DEBUG` | — | `False` (the default in prod). `True` prints a warning; use only briefly to diagnose. |
| `WEB_CONCURRENCY` | — | `2` (gunicorn workers on the free 512 MB instance) |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | — | First admin account, created by `build.sh` once. **Django skips password-strength checks here, so use a strong generated password.** The password variable can be deleted after the first deploy. |
| `RENDER_EXTERNAL_HOSTNAME` | auto | Set by Render. Added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. |
| `DJANGO_EMAIL_*` | — | Unused (nothing sends email yet) |
| **Don't set:** `DJANGO_SETTINGS_MODULE`, `PYTHON_VERSION` | | Defaults are already correct |

What production derives from these (`config/settings/prod.py`):
- `CSRF_TRUSTED_ORIGINS` = `https://<each host>` (`.example.com` → `https://*.example.com`)
- Database: `ssl_require`, `CONN_MAX_AGE=600` with health checks, and `DISABLE_SERVER_SIDE_CURSORS=True` (required for Neon's PgBouncer pooled endpoint)
- HTTPS: `SECURE_PROXY_SSL_HEADER`, SSL redirect, secure cookies, HSTS for 30 days (preload deliberately off)

## 4. First deploy (runbook)
1. **Neon:** create a project (pick a region near Render's, e.g. US East). **Connect** → enable pooling → copy the string.
2. **Cloudinary:** sign up → API Keys → copy the API environment variable.
3. **Render:** New → Web Service → connect GitHub → `ShmuelNg1212/WhatsUp` → fill in the fields from §2 → add the variables from §3 → **Create Web Service**.
4. Watch the build log. You should see static files collected, `Applying … OK` for each migration, and `Superuser created successfully`, followed by the status **Live**.
5. Smoke test:
   - `https://<app>.onrender.com/` loads.
   - Sign up, post **with an image**, and check the image URL is `res.cloudinary.com`.
   - `/admin/` is styled and your superuser can log in.
6. Delete `DJANGO_SUPERUSER_PASSWORD` from Render (optional).

**Production starts empty.** Local demo accounts and data are never deployed, because their passwords are public in docs and chat history.

## 5. Updating the live app
1. Changes go through the usual Study → Plan → Execute steps. **Run the full suite locally** (`.venv/bin/python manage.py test`), then push to `main`.
2. Render auto-deploys: `build.sh` runs (migrations included), then gunicorn restarts. If the build fails, the **previous version keeps serving**.
3. Changing **environment variables** in Render triggers a redeploy (not via GitHub).
4. **Migrations run before the new code is live.** Keep them backwards-compatible: add first, remove in a later deploy. That way the old code keeps working during the switch.
5. **Rollback:** Render dashboard → Events → redeploy an earlier deploy, or `git revert` the commit and push. Neither undoes migrations, so handle schema rollbacks case by case.

## 6. Running locally with environment variables
- **Zero configuration by default:** `runserver` and tests use SQLite and local `media/`.
- To override anything locally, create **`.env`** in the project root (gitignored; template: `.env.example`). Real environment variables beat `.env`.
- `runserver` with `DATABASE_URL` in `.env` **uses that database**. Point it at a Neon **branch**, never production, unless you mean to.
- To run production settings locally, e.g. to debug a deploy:
  ```sh
  DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=… DATABASE_URL=postgresql://… CLOUDINARY_URL=cloudinary://… ALLOWED_HOSTS=localhost \
    .venv/bin/gunicorn config.wsgi:application
  ```
  Remember `SECURE_SSL_REDIRECT`: plain `http://` requests are redirected to https.
- **Test against Postgres** (the part local SQLite can't prove). Use a **scratch Neon branch or database, never production**; Django creates and drops `test_<name>`:
  ```sh
  TEST_DATABASE_URL='postgresql://…scratch…' .venv/bin/python manage.py test
  ```
  `test.py` ignores `DATABASE_URL` on purpose, so a `.env` can't point the suite at production.

## 7. Known constraints and gotchas
| Topic | Detail |
|---|---|
| **`django-cloudinary-storage` is unmaintained** (last release 2020) | **Never add `cloudinary_storage` to `INSTALLED_APPS`** (its README says to). Its `collectstatic` override reads `STATICFILES_STORAGE`, removed in Django 5.1, which would break the build. It also raises at import without credentials, so it's referenced only from `prod.py`. `config/tests/test_cloudinary_storage.py` proves uploads work. If it ever breaks, replace it with a small in-repo `Storage` class; no model changes needed. |
| Free-tier sleep | Render sleeps after ~15 min idle (30–60 s cold start). Neon's compute also suspends when idle. |
| Upload size | 5 MB image limit (form validation), uploaded server-side to Cloudinary |
| Orphaned media | Deleting a post or ad doesn't delete its Cloudinary asset |
| Static assets | Only the Django admin uses `/static/`. App CSS comes from the Tailwind CDN (replace with a compiled build eventually; see [design-system.md](design-system.md)). |
| Tests | `config/tests/` covers the production-settings contract, local isolation, `build.sh` (POSIX, order, errexit), pinned requirements, and the Cloudinary storage contract |

## 8. Troubleshooting
| Symptom (Render logs) | Cause / fix |
|---|---|
| `ImproperlyConfigured: Environment variable X is required in production.` | Add or fix `X` in Render → Environment |
| `DATABASE_URL must point to Postgres` | `DATABASE_URL` is empty or SQLite. Paste the Neon string. |
| `could not connect` / SSL errors during `migrate` | Wrong Neon string, or the project is suspended or deleted. Re-copy the **pooled** string. |
| `DisallowedHost` / 400 Bad Request | The hostname isn't in `ALLOWED_HOSTS`. Add it; Render's own hostname is automatic. |
| Admin pages unstyled | `collectstatic` didn't run or failed. Check the build log. |
| Images broken after upload | `CLOUDINARY_URL` is wrong. Check the Cloudinary dashboard. |
| `createsuperuser` error in build | The email is already used, or the username is invalid. Fix the `DJANGO_SUPERUSER_*` values. |
| `set: Illegal option -o …` | A bash-only line was added to `build.sh`. Keep it POSIX (enforced by tests). |
