"""
Production-configuration contract.

Settings modules are imported in a subprocess with a controlled environment, because
prod settings must fail fast at import time and each environment needs a fresh process.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

REPO = Path(__file__).resolve().parents[2]

PROD_ENV = {
    "SECRET_KEY": "test-" + "x" * 60,
    "ALLOWED_HOSTS": "example.com",
    "DATABASE_URL": "postgresql://user:pass@db.example.com:5432/app",
    "CLOUDINARY_URL": "cloudinary://123:abc@demo-cloud",
}

PROBE = """
import json, sys
import django
django.setup()
from django.conf import settings as s
d = s.DATABASES["default"]
print(json.dumps({
    "DEBUG": s.DEBUG,
    "ALLOWED_HOSTS": s.ALLOWED_HOSTS,
    "CSRF_TRUSTED_ORIGINS": getattr(s, "CSRF_TRUSTED_ORIGINS", []),
    "MIDDLEWARE": s.MIDDLEWARE,
    "STORAGES": {k: v["BACKEND"] for k, v in s.STORAGES.items()},
    "INSTALLED_APPS": s.INSTALLED_APPS,
    "DB_ENGINE": d["ENGINE"],
    "DB_OPTIONS": d.get("OPTIONS", {}),
    "DB_CONN_MAX_AGE": d.get("CONN_MAX_AGE"),
    "DB_NO_SERVER_CURSORS": d.get("DISABLE_SERVER_SIDE_CURSORS", False),
    "SECURE_SSL_REDIRECT": getattr(s, "SECURE_SSL_REDIRECT", False),
    "cloudinary_storage_imported": "cloudinary_storage" in sys.modules,
}))
"""


def run_settings(module, extra_env=None, code=PROBE, args=None):
    # A minimal environment: nothing from the developer's shell leaks in.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "SYSTEMROOT") if k in os.environ}
    env.update({"DJANGO_SETTINGS_MODULE": module, "PYTHONPATH": str(REPO)})
    env.update(extra_env or {})
    cmd = [sys.executable, *(args or ["-c", code])]
    return subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)


def load(module, extra_env=None):
    result = run_settings(module, extra_env)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


class ProductionSettingsTests(SimpleTestCase):
    def test_required_variables_fail_fast_with_clear_message(self):
        for missing in PROD_ENV:
            with self.subTest(missing=missing):
                env = {k: v for k, v in PROD_ENV.items() if k != missing}
                result = run_settings("config.settings.prod", env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"Environment variable {missing} is required in production.", result.stderr)

    def test_sqlite_database_is_refused(self):
        result = run_settings("config.settings.prod", {**PROD_ENV, "DATABASE_URL": "sqlite:///db.sqlite3"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL must point to Postgres", result.stderr)

    def test_debug_defaults_to_false(self):
        self.assertFalse(load("config.settings.prod", PROD_ENV)["DEBUG"])

    def test_debug_comes_from_environment_with_warning(self):
        result = run_settings("config.settings.prod", {**PROD_ENV, "DEBUG": "True"})
        self.assertTrue(json.loads(result.stdout.strip().splitlines()[-1])["DEBUG"])
        self.assertIn("WARNING: DEBUG is on", result.stderr)

    def test_whitenoise_directly_after_security_middleware(self):
        middleware = load("config.settings.prod", PROD_ENV)["MIDDLEWARE"]
        i = middleware.index("django.middleware.security.SecurityMiddleware")
        self.assertEqual(middleware[i + 1], "whitenoise.middleware.WhiteNoiseMiddleware")

    def test_storage_backends(self):
        storages = load("config.settings.prod", PROD_ENV)["STORAGES"]
        self.assertEqual(storages["default"], "cloudinary_storage.storage.MediaCloudinaryStorage")
        self.assertEqual(storages["staticfiles"], "whitenoise.storage.CompressedManifestStaticFilesStorage")

    def test_cloudinary_storage_app_not_installed(self):
        # Its collectstatic override reads STATICFILES_STORAGE (removed in Django 5.1).
        apps = load("config.settings.prod", PROD_ENV)["INSTALLED_APPS"]
        self.assertFalse([a for a in apps if "cloudinary" in a])

    def test_postgres_with_ssl_pooling_safe_cursors_and_persistent_connections(self):
        cfg = load("config.settings.prod", PROD_ENV)
        self.assertEqual(cfg["DB_ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(cfg["DB_OPTIONS"].get("sslmode"), "require")
        self.assertTrue(cfg["DB_NO_SERVER_CURSORS"])
        self.assertEqual(cfg["DB_CONN_MAX_AGE"], 600)

    def test_hosts_include_render_hostname_and_csrf_origins(self):
        cfg = load("config.settings.prod", {**PROD_ENV, "ALLOWED_HOSTS": "example.com,.example.org",
                                            "RENDER_EXTERNAL_HOSTNAME": "whatsup.onrender.com"})
        self.assertEqual(cfg["ALLOWED_HOSTS"], ["example.com", ".example.org", "whatsup.onrender.com"])
        self.assertEqual(cfg["CSRF_TRUSTED_ORIGINS"],
                         ["https://example.com", "https://*.example.org", "https://whatsup.onrender.com"])

    def test_render_hostname_alone_satisfies_allowed_hosts(self):
        env = {k: v for k, v in PROD_ENV.items() if k != "ALLOWED_HOSTS"}
        cfg = load("config.settings.prod", {**env, "RENDER_EXTERNAL_HOSTNAME": "whatsup.onrender.com"})
        self.assertEqual(cfg["ALLOWED_HOSTS"], ["whatsup.onrender.com"])

    def test_https_hardening(self):
        self.assertTrue(load("config.settings.prod", PROD_ENV)["SECURE_SSL_REDIRECT"])

    def test_deploy_checks_pass(self):
        result = run_settings("config.settings.prod", PROD_ENV, args=["manage.py", "check", "--deploy", "--fail-level", "WARNING"])
        output = result.stdout + result.stderr
        # The only accepted warning is HSTS preload (a deliberate Gardener decision).
        issues = [line for line in output.splitlines() if line.startswith("?:")]
        self.assertEqual([i for i in issues if "security.W021" not in i], [], output)


class LocalSettingsTests(SimpleTestCase):
    def test_dev_needs_no_environment(self):
        cfg = load("config.settings.dev")
        self.assertTrue(cfg["DEBUG"])
        self.assertEqual(cfg["DB_ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["STORAGES"]["default"], "django.core.files.storage.FileSystemStorage")
        self.assertFalse(cfg["cloudinary_storage_imported"])

    def test_dev_reads_database_url_when_given(self):
        cfg = load("config.settings.dev", {"DATABASE_URL": "postgresql://u:p@localhost:5432/dev"})
        self.assertEqual(cfg["DB_ENGINE"], "django.db.backends.postgresql")

    def test_tests_ignore_database_url_and_stay_local(self):
        cfg = load("config.settings.test", {"DATABASE_URL": "postgresql://u:p@prod.example.com/app",
                                            "CLOUDINARY_URL": PROD_ENV["CLOUDINARY_URL"]})
        self.assertEqual(cfg["DB_ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["STORAGES"]["default"], "django.core.files.storage.FileSystemStorage")
        self.assertFalse(cfg["cloudinary_storage_imported"])

    def test_tests_can_opt_into_postgres(self):
        cfg = load("config.settings.test", {"TEST_DATABASE_URL": "postgresql://u:p@localhost:5432/scratch"})
        self.assertEqual(cfg["DB_ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(cfg["DB_OPTIONS"].get("sslmode"), "require")


class BuildScriptTests(SimpleTestCase):
    script = REPO / "build.sh"

    def test_is_executable_and_valid_bash(self):
        self.assertTrue(os.access(self.script, os.X_OK))
        self.assertEqual(subprocess.run(["bash", "-n", str(self.script)]).returncode, 0)

    def test_contents(self):
        text = self.script.read_text()
        for expected in (
            "set -o errexit",
            'DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"',
            "pip install -r requirements.txt",
            "python manage.py collectstatic --no-input",
            "python manage.py migrate --no-input",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        # Order matters: dependencies → static → schema.
        self.assertLess(text.index("pip install"), text.index("collectstatic"))
        self.assertLess(text.index("collectstatic"), text.index("migrate --no-input"))

    def test_requirements_pin_production_stack(self):
        reqs = (REPO / "requirements.txt").read_text()
        for package in ("Django==", "gunicorn==", "whitenoise==", "psycopg2-binary==", "dj-database-url==",
                        "django-environ==", "cloudinary==", "django-cloudinary-storage=="):
            with self.subTest(package=package):
                self.assertIn(package, reqs)
