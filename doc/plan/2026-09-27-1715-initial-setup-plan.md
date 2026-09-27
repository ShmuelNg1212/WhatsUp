# Plan: Initial Setup (Phase 1: Foundation)
- **Date:** 2026-09-27 17:15
- **Study:** [../study/2026-09-27-1715-project-initialization.md](../study/2026-09-27-1715-project-initialization.md)
- **Status:** in-progress

## Tasks
- [ ] 1. Create `.venv` from Homebrew Python 3.14, pin `Django==6.1.1` in `requirements.txt`, run `django-admin startproject config .` → `build: bootstrap django 6.1 project`
- [ ] 2. Split settings into `config/settings/{base,dev,test,prod}.py`; `manage.py` defaults to `dev`; `prod` requires `DJANGO_SECRET_KEY` + `DJANGO_ALLOWED_HOSTS`; add `.env.example` → `build: split settings by environment`
- [ ] 3. Create `accounts` app: `User(AbstractUser)` with `Role` TextChoices, unique case-insensitive email, role CheckConstraint, role helpers; set `AUTH_USER_MODEL`; generate the **first** migration; register in admin → `feat(accounts): add custom user model with regular and advertiser roles`
- [ ] 4. Model tests for User: default role, role helpers, invalid role rejected by DB, case-insensitive email uniqueness, superuser creation → `test(accounts): cover user model constraints`
- [ ] 5. Create `ads` app: `AdvertiserProfile` (OneToOne → User) with `clean()` enforcing advertiser-only; admin inline; migration → `feat(ads): add advertiser profile model`
- [ ] 6. Tests for AdvertiserProfile: one per user, rejects regular users, cascade delete → `test(ads): cover advertiser profile constraints`
- [ ] 7. Role gating: `accounts/permissions.py` with `RoleRequiredMixin` + `role_required` (anon → login redirect, wrong role → 403) → `feat(accounts): add role-based view protection`
- [ ] 8. Base templates: `templates/base.html` (Tailwind CDN, nav showing auth state/role), landing page, 403 page → `feat: add base layout and landing page`
- [ ] 9. Auth flows: built-in login/logout, regular signup and advertiser signup (atomic user+profile), `home` role router, templates → `feat(accounts): add signup, login, logout and role-based home routing`
- [ ] 10. Gated placeholder areas: `posts` app `/feed/` (REGULAR_USER only), `ads` `/ads/` dashboard (ADVERTISER only) → `feat: add role-gated feed and advertiser dashboard`
- [ ] 11. Tests: signup flows (role assignment, profile creation, atomicity, validation), login/logout, home routing, gating matrix (anon/regular/advertiser × feed/ads) for both mixin and decorator → `test: cover authentication flows and role gating`
- [ ] 12. Verify: `manage.py check`, `check --deploy --settings=config.settings.prod` (sanity), `makemigrations --check`, full test suite green, dev server smoke test via HTTP → fix commits as needed

## Blocked On
Nothing.
