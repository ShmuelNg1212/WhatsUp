"""
Production settings (Render.com + Neon Postgres + Cloudinary).

Everything sensitive comes from the environment; see doc/wiki/deployment.md.
Required:  SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL (Postgres), CLOUDINARY_URL
Optional:  DEBUG (default False), RENDER_EXTERNAL_HOSTNAME (set by Render automatically),
           DJANGO_EMAIL_* (unused until the app sends email)
"""

import sys

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env


def _require(name):
    value = env.str(name, default="")
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required in production.")
    return value


SECRET_KEY = _require("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)
if DEBUG:
    print("WARNING: DEBUG is on in production settings; error pages will expose configuration.", file=sys.stderr)

# Hosts: ALLOWED_HOSTS (comma-separated) plus Render's own hostname, which Render
# injects as RENDER_EXTERNAL_HOSTNAME (e.g. whatsup.onrender.com).
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
_render_host = env.str("RENDER_EXTERNAL_HOSTNAME", default="")
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Environment variable ALLOWED_HOSTS is required in production.")
CSRF_TRUSTED_ORIGINS = [
    f"https://*{host}" if host.startswith(".") else f"https://{host}"
    for host in ALLOWED_HOSTS
    if host != "*"
]

# Database: Neon Postgres. The disk on Render is ephemeral, so SQLite is refused.
_database_url = _require("DATABASE_URL")
if _database_url.startswith("sqlite"):
    raise ImproperlyConfigured("DATABASE_URL must point to Postgres in production (the server disk is ephemeral).")
DATABASES = {
    "default": {
        **dj_database_url.parse(_database_url, conn_max_age=600, conn_health_checks=True, ssl_require=True),
        # Neon's pooled endpoint uses PgBouncer in transaction mode.
        "DISABLE_SERVER_SIDE_CURSORS": True,
    },
}

# Storage: uploads → Cloudinary, static files → WhiteNoise (compressed, hashed).
# cloudinary_storage reads CLOUDINARY_URL itself; check it first for a clear error.
# NB: cloudinary_storage is deliberately NOT in INSTALLED_APPS: its collectstatic
# override reads STATICFILES_STORAGE, which Django 5.1+ removed (see doc/wiki/deployment.md).
_require("CLOUDINARY_URL")
STORAGES = {
    "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HTTPS (Render terminates TLS and forwards X-Forwarded-Proto).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# HSTS preload is deliberately off: submitting a domain to the browser preload
# list is hard to undo, so it is a Gardener decision once a domain exists.

# Nothing sends email yet. SMTP credentials are an exogenous input needed
# before password reset / notifications ship (see doc/wiki/external-dependencies.md).
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": env.str("DJANGO_EMAIL_HOST", default="localhost"),
            "port": env.int("DJANGO_EMAIL_PORT", default=587),
            "username": env.str("DJANGO_EMAIL_HOST_USER", default=""),
            "password": env.str("DJANGO_EMAIL_HOST_PASSWORD", default=""),
            "use_tls": True,
        },
    },
}
