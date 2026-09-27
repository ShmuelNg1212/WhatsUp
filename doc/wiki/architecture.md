# Architecture

## Stack
| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Framework | Django 6.1.1 (the only runtime dependency) |
| Database | SQLite (development) |
| Frontend | Server-rendered Django templates + Tailwind CSS v4 browser CDN (dev only; needs a compiled build before production) |
| Auth | `django.contrib.auth` with a custom user model |
| Tests | Django's built-in test runner (`TestCase`) |

## Project layout
```
config/            project package: settings/{base,dev,test,prod}.py, urls.py, wsgi/asgi
accounts/          identity: User model, signup/login/logout, role permissions, home router
posts/             the social area for regular users
ads/               the advertiser area: AdvertiserProfile, dashboard
templates/         all templates (project-level, grouped by app)
doc/               study/ (decisions), plan/ (checklists), wiki/ (this)
```
Each app keeps its tests in `<app>/tests/`.

## Roles and access control
Every account is an `accounts.User` with a `role`: `REGULAR_USER` or `ADVERTISER`. The areas are **exclusive**. Advertisers are business-only accounts and cannot use the social area.

Gating helpers are in `accounts/permissions.py`:
- `RoleRequiredMixin` (class-based views): set `allowed_roles = (...)`
- `@role_required(*roles)` (function views)

Both apply the same rules:
| Visitor | Result |
|---|---|
| Anonymous | 302 → `/accounts/login/?next=<path>` |
| Logged in, role not allowed | 403 (`templates/403.html`) |
| Logged in, role allowed | View runs |

Staff and superuser status gives **no** bypass. Admins use `/admin/`.

## URL map
| Path | Name | Access |
|---|---|---|
| `/` | `home` | Anonymous → landing page. Regular user → `/feed/`. Advertiser → `/ads/` |
| `/accounts/signup/` | `signup` | Anonymous (logged-in users redirected home) |
| `/accounts/signup/advertiser/` | `signup_advertiser` | Anonymous |
| `/accounts/login/` | `login` | Anyone |
| `/accounts/logout/` | `logout` | POST only |
| `/feed/` | `posts:feed` | `REGULAR_USER` |
| `/ads/` | `ads:dashboard` | `ADVERTISER` |
| `/admin/` | Django admin | Staff |

## Key flows
- **Signup:** each role has its own form (`accounts/forms.py`). The form sets the role on the server, so it can't be chosen via POST data. Advertiser signup creates the `User` and `AdvertiserProfile` inside one `transaction.atomic()`. The user is logged in after signup and redirected to `home`.
- **Login and logout:** Django's built-in `LoginView` and `LogoutView`. After login, `home` sends the user to their role's area.
