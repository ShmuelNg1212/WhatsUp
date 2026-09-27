"""Settings for the automated test suite."""

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = "django-insecure-test-only"

ALLOWED_HOSTS = ["testserver", "localhost"]

# Fast hashing keeps the suite quick; never use outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    },
}
