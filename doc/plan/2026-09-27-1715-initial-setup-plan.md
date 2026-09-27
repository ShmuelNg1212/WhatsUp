# Plan: Initial Setup (Phase 1: Foundation)
- **Date:** 2026-09-27 17:15
- **Study:** [../study/2026-09-27-1715-project-initialization.md](../study/2026-09-27-1715-project-initialization.md)
- **Status:** awaiting-rendezvous

## Tasks
- [x] 1. Create `.venv` from Homebrew Python 3.14, pin `Django==6.1.1` in `requirements.txt`, run `django-admin startproject config .` → `build: bootstrap django 6.1 project`
- [x] 2. Split settings into `config/settings/{base,dev,test,prod}.py`. `manage.py` defaults to `dev` (`test` for the `test` command). `wsgi`/`asgi` default to `prod`. `prod` requires `DJANGO_SECRET_KEY` + `DJANGO_ALLOWED_HOSTS`. Add `.env.example` → `build: split settings by environment`
- [x] 3. Create `accounts` app: `User(AbstractUser)` with `Role` TextChoices, unique case-insensitive email, role CheckConstraint, role helpers. Set `AUTH_USER_MODEL`. Generate the **first** migration. Register in admin → `feat(accounts): add custom user model with regular and advertiser roles`
  - _Deviation:_ empty `posts`/`ads` app skeletons committed first as `chore: scaffold posts and ads apps`.
- [x] 4. Model tests for User → `test(accounts): cover user model constraints`
- [x] 5. Create `ads` app: `AdvertiserProfile` (OneToOne → User) with `clean()` enforcing advertiser-only. Admin. Migration → `feat(ads): add advertiser profile model`
  - _Deviation:_ standalone admin instead of an inline on the User admin, so `accounts` stays independent of `ads` in the admin.
- [x] 6. Tests for AdvertiserProfile → `test(ads): cover advertiser profile constraints`
- [x] 7. Role gating: `accounts/permissions.py` with `RoleRequiredMixin` + `role_required` → `feat(accounts): add role-based view protection`
- [x] 8. Base templates: `base.html` (Tailwind CDN), landing page, 403 page → `feat: add base layout and landing page`
- [x] 9. Auth flows: built-in login/logout, regular + advertiser signup (atomic user+profile) → `feat(accounts): add signup, login and logout flows`
- [x] 10. Gated areas: `/feed/` (REGULAR_USER, mixin), `/ads/` (ADVERTISER, decorator), plus the `home` role router (moved here from task 9 because it needs these routes) → `feat: add role-gated feed and advertiser dashboard with home routing`
- [x] 11. Tests: signup, login/logout, home routing, gating matrix, helper unit tests → `test: cover authentication flows and role gating`
- [x] 12. Verify:
  - `check` clean. `makemigrations --check`: no changes. Fresh `migrate` OK.
  - `check --deploy` (prod) flagged the dev mail backend → `fix(settings): use smtp mail backend in production`. The only remaining warning is HSTS preload, which is off on purpose.
  - 65/65 tests pass. A deliberate break of the feed gate made the gating tests fail, as it should.
  - Live dev-server HTTP smoke test: anonymous visitors are redirected, advertiser signup → dashboard, advertiser → `/feed/` = 403.

## Blocked On
Nothing.
