# Features

## Accounts
- Sign up as a **regular user** (username, email, password) or as an **advertiser** (plus company name and optional website).
- Log in and log out. After login, each role lands in its own area.
- Emails are unique regardless of case. Passwords go through Django's standard validators.

## Regular users
- `/feed/`: placeholder feed page.

## Advertisers
- `/ads/`: dashboard showing company details. Campaigns are not built yet.

## Admin
- Manage users (filter by role) and advertiser profiles at `/admin/`.
