"""
Local development settings. Never use in production.

Works with no environment at all (SQLite, local media/). Any variable in the
environment or a local .env file (see .env.example) overrides the defaults below.
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)

# Fallback key only ever signs local sessions; production requires SECRET_KEY (prod.py).
SECRET_KEY = env.str("SECRET_KEY", default="django-insecure-dev-only-do-not-use-in-production")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
