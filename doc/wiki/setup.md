# Setup

## Requirements
- **Python ≥ 3.12** (Django 6.1 requirement). The project `.venv` is built from Homebrew's Python 3.14 (`/opt/homebrew/opt/python@3.14/bin/python3.14`), matching `.python-version` (used by Render). The macOS system `python3` (3.9) is too old.
- **No environment variables are needed locally:** SQLite and local `media/`. The production packages in `requirements.txt` (gunicorn, psycopg2, Cloudinary, …) install fine but stay unused in dev. Production is covered in [deployment.md](deployment.md).

## First-time setup
```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
```

## Everyday commands
| Task | Command |
|---|---|
| Run dev server | `.venv/bin/python manage.py runserver` → http://127.0.0.1:8000/ |
| Run tests | `.venv/bin/python manage.py test` |
| Apply migrations | `.venv/bin/python manage.py migrate` |
| Admin | http://127.0.0.1:8000/admin/ |
| Reset a user's password | `.venv/bin/python manage.py changepassword <username>` |
| Stop the dev server | **Ctrl + C** in its terminal, or `pkill -f "manage.py runserver"` |
| Deploy | Push to `main`; Render auto-deploys ([deployment.md](deployment.md)) |

## Restarting after template-tag changes
Django registers template-tag libraries (`*/templatetags/*.py`) when the server starts. After **adding a new tag module**, restart `runserver`. Otherwise pages using it return 500 ("… is not a registered tag library"). Template and CSS edits reload automatically.

## Uploaded media
Locally, post and ad images are saved in `media/` (gitignored) and served by the dev server at `/media/…`. In production they go to Cloudinary. Passwords are stored as one-way hashes and cannot be read back; reset them instead.

## Settings modules
| Module | Used by | Notes |
|---|---|---|
| `config.settings.dev` | `manage.py` (default) | DEBUG on (env-overridable), dev-only secret key, SQLite unless `DATABASE_URL` |
| `config.settings.test` | `manage.py test` (automatic) | Always SQLite (opt-in `TEST_DATABASE_URL`), local storage, fast MD5 hashing, in-memory mail |
| `config.settings.prod` | `wsgi.py` / `asgi.py` / `build.sh` (default) | Requires `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` (Postgres), `CLOUDINARY_URL`; WhiteNoise, HTTPS hardening. See [deployment.md](deployment.md). |

Override with `DJANGO_SETTINGS_MODULE=...`. Every setting reads from the environment via django-environ; an optional gitignored **`.env`** file (template: `.env.example`) is loaded too, and real environment variables win.
