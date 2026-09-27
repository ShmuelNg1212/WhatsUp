# Data Models

## `accounts.User` (extends `AbstractUser`, table `accounts_user`)
`AUTH_USER_MODEL = "accounts.User"`

| Field | Type | Notes |
|---|---|---|
| *(AbstractUser fields)* | | `username` (unique, login ID), `password`, `first_name`, `last_name`, `is_staff`, `is_active`, `is_superuser`, `date_joined`, `last_login` |
| `email` | EmailField | **Required** (`REQUIRED_FIELDS = ["email"]`) |
| `role` | CharField(20), indexed | `User.Role`: `REGULAR_USER` (default) or `ADVERTISER` |

Constraints:
- `accounts_user_role_valid`: CHECK that `role` is one of the two values, enforced by the database.
- `accounts_user_email_ci_unique`: UNIQUE on `LOWER(email)`, so emails are unique regardless of case.

Helpers: `user.is_regular_user`, `user.is_advertiser`.

## `ads.AdvertiserProfile`
Business details for an advertiser account.

| Field | Type | Notes |
|---|---|---|
| `user` | OneToOne → User, CASCADE | `related_name="advertiser_profile"` |
| `company_name` | CharField(200) | Required |
| `website` | URLField | Optional |
| `created_at` | DateTimeField | Set automatically |

Invariant: **only `ADVERTISER` users have a profile.** The database cannot enforce a rule across two tables, so it is enforced by `clean()`, which the admin and forms call, and by atomic advertiser signup. Code that writes directly through the ORM must keep this rule itself. The dashboard handles a missing profile gracefully.

## Relationships
```
User 1 ──── 0..1 AdvertiserProfile   (only when role = ADVERTISER)
```
