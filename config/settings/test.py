"""Settings for the automated test suite."""

import dj_database_url

from .base import *  # noqa: F403
from .base import BASE_DIR, env

DEBUG = False

SECRET_KEY = "django-insecure-test-only"

ALLOWED_HOSTS = ["testserver", "localhost"]

# Always SQLite, so a DATABASE_URL in a local .env can never point the suite at
# production. To run the suite against Postgres (e.g. a Neon branch), opt in
# explicitly with TEST_DATABASE_URL; Django creates and drops a test_… database.
_test_db_url = env.str("TEST_DATABASE_URL", default="")
DATABASES = {
    "default": (
        dj_database_url.parse(_test_db_url, ssl_require=_test_db_url.startswith("postgres"))
        if _test_db_url
        else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    ),
}

# Local file storage and plain static storage: tests never touch Cloudinary.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Fast hashing keeps the suite quick; never use outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    },
}
