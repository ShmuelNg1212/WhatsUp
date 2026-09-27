"""
Production settings.

Required environment variables (documented in .env.example):
    DJANGO_SECRET_KEY      long random string
    DJANGO_ALLOWED_HOSTS   comma-separated hostnames
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


def _require_env(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required in production.")
    return value


DEBUG = False

SECRET_KEY = _require_env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = [h.strip() for h in _require_env("DJANGO_ALLOWED_HOSTS").split(",") if h.strip()]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
