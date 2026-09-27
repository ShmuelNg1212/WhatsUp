# External Dependencies

| Input | Used for | Status | Where configured |
|---|---|---|---|
| Python ≥ 3.12 | Runtime | Verified (Homebrew 3.14.7) | `.venv` |
| Django 6.1.1 (PyPI) | Framework | Verified | `requirements.txt` |
| Pillow 12.3.0 (PyPI) | Image uploads (`ImageField`) | Verified (Python 3.14 arm64 wheel) | `requirements.txt` |
| Tailwind CSS v4 browser CDN (jsDelivr) | Styling | Verified; **dev only**. Replace with a compiled build before production. | `templates/base.html` |
| Inter font (Google Fonts) | Typography | Verified (public CDN, no key) | `templates/base.html` |
| `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` | Production | Needed at deploy | env vars (see `.env.example`) |
| SMTP provider credentials | Email (nothing sends email yet) | Needed later | `DJANGO_EMAIL_*` env vars, `config/settings/prod.py` |
| Payment processor (e.g. Stripe) | Charging campaign budgets (budgets are stored only, as USD) | Needed before real ad spend | — |
| Hosting target and domain | Production | Needed later | — |
| Production media storage (S3/GCS/R2 or a web server) | Serving uploaded post and ad images when `DEBUG=False` | Needed before deploy | `MEDIA_*` settings / `STORAGES` |
