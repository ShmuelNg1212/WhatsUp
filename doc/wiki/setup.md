# Setup

## Requirements
- **Python ≥ 3.12** (Django 6.1 requirement). The project `.venv` is built from Homebrew's Python 3.14 (`/opt/homebrew/opt/python@3.14/bin/python3.14`). The macOS system `python3` (3.9) is too old.

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

## Settings modules
| Module | Used by | Notes |
|---|---|---|
| `config.settings.dev` | `manage.py` (default) | DEBUG on, dev-only secret key, SQLite |
| `config.settings.test` | `manage.py test` (automatic) | Fast MD5 password hashing, in-memory mail |
| `config.settings.prod` | `wsgi.py` / `asgi.py` (default) | Requires env vars (see `.env.example`), HTTPS hardening, SMTP mail |

Override with `DJANGO_SETTINGS_MODULE=...`. Dev and test need no environment variables.
