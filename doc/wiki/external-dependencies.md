# External Dependencies

| Input | Used for | Status | Where configured |
|---|---|---|---|
| Python ≥ 3.12 | Runtime | Verified (Homebrew 3.14.7) | `.venv` |
| Django 6.1.1 (PyPI) | Framework | Verified | `requirements.txt` |
| Tailwind CSS v4 browser CDN (jsDelivr) | Styling | Verified; **dev only** | `templates/base.html` |
| `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` | Production | Needed at deploy | env vars (see `.env.example`) |
| SMTP provider credentials | Email (nothing sends email yet) | Needed later | `DJANGO_EMAIL_*` env vars, `config/settings/prod.py` |
| Payment processor (e.g. Stripe) | Buying ad units | Needed later | — |
| Hosting target and domain | Production | Needed later | — |
