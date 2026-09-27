"""Local development settings. Never use in production."""

from .base import *  # noqa: F403

DEBUG = True

# Dev-only key; production reads DJANGO_SECRET_KEY from the environment (see prod.py).
SECRET_KEY = "django-insecure-dev-only-do-not-use-in-production"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
