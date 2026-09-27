# Study: Project Initialization (Phase 1: Foundation)
- **Date:** 2026-09-27 17:15
- **Request:** Kick off a Django social media application (feeds, posts, likes/comments, following) that treats advertising as a core feature: a separate Advertiser role creates campaigns and buys sponsored units that appear natively in user feeds. Phase 1 builds the foundation: stack, custom user model with `REGULAR_USER` / `ADVERTISER` roles, role-based view protection, a modular app structure, settings split by environment, and a thorough test suite.

## Intended Outcome
A runnable Django project that the Gardener can start locally, where:
- A visitor can sign up as a **regular user** or as an **advertiser** (with company details).
- A visitor can log in and log out. After login, each role lands in its own area.
- Regular users can reach the social area (`/feed/`) and **cannot** reach the advertiser area (`/ads/`).
- Advertisers can reach the advertiser area (`/ads/`) and **cannot** reach the regular user area (`/feed/`).
- Anonymous visitors who open a protected page are redirected to login.
- Both roles can be managed in the Django admin.
- `python manage.py test` passes and covers authentication, role gating, and model constraints.

**Acceptance criteria**
- [ ] `migrate` runs cleanly on a fresh SQLite database.
- [ ] Both signup flows create an account of the correct role. Advertiser signup also creates an advertiser profile, in one atomic step.
- [ ] Opening the other role's area as a logged-in user returns **403 Forbidden**.
- [ ] Opening a protected page anonymously redirects to `/accounts/login/?next=...`.
- [ ] The test suite passes with no failures.

## Current State
Empty repository: only `AGENTS.md`, `CLAUDE.md`, `.gitignore`, and the `doc/` scaffold.

**Environment facts (verified 2026-09-27):**
- Latest stable Django on PyPI: **6.1.1**, which requires **Python ≥ 3.12**.
- The macOS system `python3` is **3.9.6**, too old for it.
- Homebrew has **Python 3.14.7** installed at `/opt/homebrew/opt/python@3.14/bin/python3.14`, which Django 6.1 supports. The project will use a `.venv` built from it.

## Options & Tradeoffs

### A. Modeling user roles

| Option | Pros | Cons | Effort | Risk |
|---|---|---|---|---|
| **A1. Single `User` + `role` TextChoices field** | One auth table. Checking a role is a field read with no join. Works directly with `AUTH_USER_MODEL`, the admin, and the auth views. Easy to query (`User.objects.filter(role=...)`). | Role-specific data (company name, billing) would fill `User` with nullable columns that don't apply to most rows. | Low | Low |
| **A2. Separate profile models only** (`RegularProfile`, `AdvertiserProfile`, role inferred from which one exists) | Clean per-role data | The role is implicit: every check becomes `hasattr(user, 'advertiserprofile')` plus a join. It is possible to end up with a user who has zero or two profiles. Harder to query. | Medium | Medium |
| **A3. Hybrid: `role` field on `User` + `AdvertiserProfile` (OneToOne) for advertiser-only data** | Role checks are explicit and cheap (A1). Advertiser business and billing data stays in its own table and can grow (billing address, tax ID, payment customer ID) without touching `User`. Regular users need no profile row. | Two sources of truth to keep in step: role=ADVERTISER should always have a profile. The database cannot enforce a rule that spans two tables, so the application enforces it. | Low–Medium | Low |
| **A4. Multi-table inheritance / proxy models** (`Advertiser(User)`) | Type-level separation | MTI adds implicit joins and is awkward with `AUTH_USER_MODEL`. Proxy models share one table, so they add nothing over A1 for storing data. Neither fits how Django's auth framework is normally used. | Medium | Medium |

### B. Settings layout

| Option | Pros | Cons |
|---|---|---|
| **B1. `config/settings/{base,dev,test,prod}.py` package** | Common Django pattern. Each environment explicitly overrides the shared base. No new dependencies. | Several files to keep consistent |
| B2. Single `settings.py` + `django-environ` | One file | Adds a dependency. Environment differences are hidden in env variables. |

### C. Authentication views

| Option | Pros | Cons |
|---|---|---|
| **C1. Django built-in `django.contrib.auth` views + two custom signup `CreateView`s** | Uses framework defaults, adds no dependencies, and is secure (CSRF protection, password validators) | Signup is written by hand, but it is small |
| C2. `django-allauth` | Email verification and social login ready | Heavy for Phase 1. Its opinions would need customizing for role-based signup. Can be added later if email verification or social login becomes a requirement. |

### D. Test runner

| Option | Pros | Cons |
|---|---|---|
| **D1. Django's built-in runner (`manage.py test`, `TestCase`)** | Framework default, zero dependencies | More verbose than pytest |
| D2. pytest + pytest-django | Short tests, fixtures | Adds dependencies. Can be adopted later without rewriting (pytest runs `TestCase` classes). |

## Recommendation

**A3 (Hybrid)**, **B1**, **C1**, **D1**, which keep dependencies to Django only.

**User model** (`accounts.User(AbstractUser)`):
- `role = CharField(choices=User.Role, default=Role.REGULAR_USER)` with `Role(TextChoices)`: `REGULAR_USER`, `ADVERTISER`.
- `email` is required (`REQUIRED_FIELDS = ["email"]`) and **unique regardless of case**, enforced by a `UniqueConstraint(Lower("email"))`.
- DB `CheckConstraint`: `role IN ('REGULAR_USER', 'ADVERTISER')`, so invalid roles can't slip in through raw SQL or bulk operations.
- Helper properties: `is_advertiser`, `is_regular_user`.
- Login uses **username** (the `AbstractUser` default). Email is collected and unique, so switching to email login later is a small change.

**AdvertiserProfile** (`ads.AdvertiserProfile`, `OneToOneField(User, related_name="advertiser_profile")`):
- `company_name` (required), `website` (optional), `created_at`.
- It lives in the `ads` app because it is business data for the advertising product and will sit next to future `Campaign` and `AdUnit` models.
- **Invariant:** only users with role=ADVERTISER may have a profile. Enforced in `clean()` (admin and forms) and covered by tests. The advertiser signup form creates the user and profile together in one `transaction.atomic()` block.

**Role gating** (`accounts/permissions.py`):
- `RoleRequiredMixin` for class-based views and `role_required` for function views. Both build on Django's `LoginRequiredMixin` / `user_passes_test` conventions.
- Anonymous visitors are redirected to login (`?next=`). Authenticated users with the wrong role get **403**. Being logged in but unauthorized is a different case from not being logged in.
- After login, `LOGIN_REDIRECT_URL = "home"`. A `home` view sends each role to its own area. Anonymous visitors see a landing page with both signup options.

**Directory structure** (Django defaults: apps at the project root, one project config package):
```
WhatsUp/
├── manage.py
├── requirements.txt          # Django==6.1.1 (pinned)
├── .env.example              # documents env vars (none secret in dev)
├── config/                   # project package
│   ├── settings/{__init__,base,dev,test,prod}.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
├── accounts/                 # User model, signup/login, role permissions, home router
├── posts/                    # social area: Phase 1 = gated feed placeholder
├── ads/                      # advertiser area: AdvertiserProfile + gated dashboard placeholder
├── templates/                # project-level: base.html, registration/, per-app folders
└── doc/
```

**Frontend:** vanilla Django templates styled with the **Tailwind CSS v4 browser CDN** (`@tailwindcss/browser@4` via jsDelivr). This is fine for development. It will be replaced with a compiled build before production (the browser build is not meant for production).

**Scope boundary:** Phase 1 creates the `posts` and `ads` apps with gated placeholder pages only. The `Post`, `Like`, `Comment`, `Follow`, `Campaign`, and `AdUnit` models are Phase 2+. Adding them later needs no rework of the foundation.

## Exogenous Inputs
| Input | Why needed | Status | Owner |
|---|---|---|---|
| Python ≥ 3.12 on dev machine | Django 6.1 requirement | **verified**: Homebrew Python 3.14.7 present | Vine |
| Tailwind CSS browser CDN | Styling | **verified**: public CDN, no key | Vine |
| Payment processor (e.g. Stripe) account + API keys | Buying ad units: **not Phase 1** | needed later | Gardener |
| Production hosting / domain | `prod.py` settings (`ALLOWED_HOSTS`, DB) | needed later | Gardener |

No external inputs block Phase 1.

## Risks & Open Questions

**Product defaults assumed.** These are cheap to change now and flagged for the Gardener at Rendezvous:
1. **Advertisers are business-only accounts in Phase 1.** They cannot reach the social area (`/feed/`). If advertisers should also post and follow as normal users, gating changes from "exclusive" to "additive", which is a small change.
2. **Roles are fixed at signup.** Only an admin can change a user's role. Switching roles in the UI is not supported.
3. **Login uses username.** Email is required and unique but is not the login identifier.
4. **No email verification in Phase 1.** Could be added via `django-allauth` or a custom flow later.

**Technical risks**
- The custom user model **must** exist before the first `migrate`. This is handled by building `accounts` first and generating migrations only after `AUTH_USER_MODEL` is set.
- The profile↔role rule is enforced by the application, not the database, so direct ORM writes could break it. This is mitigated by `clean()`, atomic signup, and tests. A `post_save` guard can be reconsidered if other write paths appear.
- The Tailwind browser CDN is not for production (noted above).
