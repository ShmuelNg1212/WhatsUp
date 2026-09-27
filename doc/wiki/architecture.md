# Architecture

## Stack
| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Framework | Django 6.1.1 |
| Image handling | Pillow 12.3.0 (required by `ImageField`) |
| Database | SQLite (development) |
| Frontend | Server-rendered Django templates + Tailwind CSS v4 browser CDN (dev only; needs a compiled build before production). No JavaScript: every interaction is an HTML form POST. |
| Auth | `django.contrib.auth` with a custom user model |
| Tests | Django's built-in test runner (`TestCase`) |

## Project layout
```
config/            project package: settings/{base,dev,test,prod}.py, urls.py, wsgi/asgi
accounts/          identity + social graph: User, Follow, signup/login/logout, role permissions, home router
posts/             the social area: Post, Like, Comment, feed/profile/people views, query builders
ads/               the advertiser portal: AdvertiserProfile, Campaign, AdUnit, ownership mixins, CRUD views
core/              plain package (not an app) with shared helpers: core/validators.py (image size)
templates/         all templates, grouped by app; posts/_*.html are reusable partials
media/             user uploads (gitignored)
doc/               study/ (decisions), plan/ (checklists), wiki/ (this)
```
Each app keeps its tests in `<app>/tests/`.

**App dependencies point one way:** `posts → accounts`, `ads → accounts`, and both use `core`. `accounts` imports `ads` only in the advertiser signup form. `ads` never imports `posts` at runtime.

## Roles and access control
Every account is an `accounts.User` with a `role`: `REGULAR_USER` or `ADVERTISER`. The areas are **exclusive**:
- The **social area** (feed, posts, profiles, people, likes, comments, follows) is for `REGULAR_USER` only.
- The **advertiser portal** (`/ads/…`) is for `ADVERTISER` only. Advertisers have no profile page and cannot be followed.
- Inside the portal, a second layer, **object ownership**, limits each advertiser to their own campaigns and ads. See [Advertiser portal](#advertiser-portal).

Gating helpers are in `accounts/permissions.py`:
- `RoleRequiredMixin` (class-based views): set `allowed_roles = (...)`. The social views share `posts.views.RegularUserRequiredMixin`.
- `@role_required(*roles)` (function views)

| Visitor | Result |
|---|---|
| Anonymous | 302 → `/accounts/login/?next=<path>` |
| Logged in, role not allowed | 403 (`templates/403.html`) |
| Logged in, role allowed | View runs |

Staff and superuser status gives **no** bypass. Admins use `/admin/`.

## URL map
| Path | Name | Method | Access |
|---|---|---|---|
| `/` | `home` | GET | Anonymous → landing. Regular → `/feed/`. Advertiser → `/ads/` |
| `/accounts/signup/` | `signup` | GET/POST | Anonymous |
| `/accounts/signup/advertiser/` | `signup_advertiser` | GET/POST | Anonymous |
| `/accounts/login/` | `login` | GET/POST | Anyone |
| `/accounts/logout/` | `logout` | POST | Logged in |
| `/feed/` | `posts:feed` | GET (feed), POST (create post) | Regular |
| `/posts/<id>/` | `posts:detail` | GET | Regular |
| `/posts/<id>/like/` | `posts:like` | POST (toggle) | Regular |
| `/posts/<id>/comments/` | `posts:comment` | POST | Regular |
| `/people/` | `posts:people` | GET | Regular |
| `/u/<username>/` | `posts:profile` | GET | Regular (404 for advertisers or unknown users) |
| `/u/<username>/follow/` | `posts:follow` | POST (toggle) | Regular |
| `/ads/` | `ads:dashboard` | GET | Advertiser |
| `/ads/campaigns/new/` | `ads:campaign_create` | GET/POST | Advertiser |
| `/ads/campaigns/<pk>/` | `ads:campaign_detail` | GET | Advertiser, **owner only** |
| `/ads/campaigns/<pk>/edit/` | `ads:campaign_update` | GET/POST | Advertiser, owner only |
| `/ads/campaigns/<pk>/delete/` | `ads:campaign_delete` | GET (confirm) / POST (delete) | Advertiser, owner only |
| `/ads/campaigns/<campaign_pk>/units/new/` | `ads:adunit_create` | GET/POST | Advertiser, owner of the campaign |
| `/ads/campaigns/<campaign_pk>/units/<pk>/edit/` | `ads:adunit_update` | GET/POST | Advertiser, owner; unit must be in that campaign |
| `/ads/campaigns/<campaign_pk>/units/<pk>/delete/` | `ads:adunit_delete` | GET (confirm) / POST (delete) | Advertiser, owner; unit must be in that campaign |
| `/media/<path>` | — | GET | Anyone; **served only when `DEBUG=True`** |
| `/admin/` | Django admin | — | Staff |

Social toggle and create endpoints reject GET with 405. Portal delete routes use GET for the confirmation page and POST to delete.

## The organic feed
**Membership:** a user's feed contains their **own posts** plus posts by **everyone they follow**, newest first (`-created_at, -id`), with 20 per page.

**Query strategy (fan-out on read).** All post lists go through `posts/queries.py`:

| Function | Used by | What it adds |
|---|---|---|
| `annotated_posts(viewer, comment_limit=None)` | post detail (all comments) | `select_related("author")`. `like_count` and `comment_count` (SQL `COUNT DISTINCT`). `liked_by_me` (`EXISTS` subquery). Comments prefetched into `post.shown_comments` with their authors joined in. |
| `feed_for(user)` | `/feed/` | The query above filtered to `author = user OR author IN (subquery of followed ids)`, with the latest **3** comments per post (a sliced prefetch using window functions) |
| `posts_by(author, viewer)` | `/u/<username>/` | Same, filtered to one author |
| `oldest_first_previews(posts)` | feed, profile | Flips the newest-first comment previews into reading order |

**Queries per page are fixed, whatever the amount of content.** `posts/tests/test_queries.py` locks these numbers:

| Page | Queries | Breakdown |
|---|---|---|
| Feed | 5 | session, user, paginator count, posts (with authors, counts, liked_by_me), comment previews |
| Profile | 7 | session, user, profile user (with follow counts), paginator count, posts, comment previews, is-following check |
| Post detail | 4 | session, user, post, all comments |
| People | 4 | session, user, paginator count, people (with counts and followed_by_me) |

If any of these tests fails, a template or view has started running a query per item. Fix the query builder; don't change the expected numbers.

**Scaling notes:** `COUNT DISTINCT` over two joins is fine at this scale. The next steps would be subquery counts, then cached counters, then fan-out on write. The query builder isolates this, so views and templates won't change. Sponsored ads (next slice) will be merged into the feed at the view layer, rendered with `ads/_ad_card.html`.

## Advertiser portal

### Permission model: two layers on every view
| Layer | Question | Where | Failure |
|---|---|---|---|
| 1. Role | Is this a logged-in `ADVERTISER`? | `ads.mixins.AdvertiserRequiredMixin` (`RoleRequiredMixin`), in `dispatch()` before any query | Anonymous → 302 login. Other roles, including superusers → **403** |
| 2. Ownership | Does *this* record belong to *this* advertiser? | Querysets pre-filtered to `request.user`, in `ads/mixins.py` | **404**, so the record's existence isn't revealed |

- `campaigns_owned_by(user)` → `Campaign.objects.filter(advertiser=user)`. This is the **only** way portal code fetches campaigns.
- `OwnedCampaignMixin.get_queryset()` returns that queryset. Django's generic `DetailView`, `UpdateView`, and `DeleteView` fetch `pk` through it, so a foreign ID is simply not found.
- `OwnedAdUnitMixin` resolves `self.campaign` from `campaign_pk` through the owned queryset at the **start** of `get()`/`post()` (404 before any form or upload handling). It then restricts units to `AdUnit.objects.filter(campaign=self.campaign)`, so a unit must belong to that exact campaign.
- **No mass-assignment:** `advertiser` and `campaign` are never form fields. The views set them on the server (`form.instance.advertiser = request.user`, `form.instance.campaign = self.campaign`). Forms list their fields explicitly.
- Deletion uses Django's `DeleteView`: GET shows a confirmation page, and only a POST with a CSRF token deletes.

**Rule for new portal views:** inherit `OwnedCampaignMixin` or `OwnedAdUnitMixin` (or `AdvertiserRequiredMixin` plus `campaigns_owned_by()`). Never call `Campaign.objects.get(...)` or `AdUnit.objects.get(...)` directly in a portal view. `ads/tests/test_permissions.py` checks every route against anonymous, regular, superuser, other-advertiser, and owner actors, with GET and POST, and verifies the database is unchanged after every refusal. **Add every new route to that matrix.**

### Views
All are Django generic views, with success messages from `SuccessMessageMixin`.

| View | Base | Notes |
|---|---|---|
| `DashboardView` | `TemplateView` | Company details. Stats (campaign count, live count, total budget) are computed from one campaign query annotated with `ad_count`. |
| `CampaignCreateView` / `CampaignUpdateView` | `CreateView` / `UpdateView` | `CampaignForm(advertiser=request.user)` |
| `CampaignDetailView` | `DetailView` | Campaign parameters + an ad preview for each unit |
| `CampaignDeleteView` | `DeleteView` | Confirmation page warns about the N ad units that will be deleted too |
| `AdUnitCreateView` / `AdUnitUpdateView` / `AdUnitDeleteView` | `CreateView` / `UpdateView` / `DeleteView` | Nested under the campaign. Success goes back to the campaign page. |

### Form rules
- `CampaignForm`: name unique per advertiser, **case-insensitive**. This is checked in `clean_name`, because Django skips the `(advertiser, name)` model constraint when `advertiser` isn't on the form. Budget ≥ 0.01. End ≥ start. **A new campaign can't start in the past**, but an existing one may keep a past start date. Dates use `<input type="date">`.
- `AdUnitForm`: target URL defaults to `https://` when no scheme is given, and only `http`/`https` are allowed (model validator). Image ≤ 5 MB (`core.validators.validate_image_size`) and must be a real image (Pillow).

### Campaign state (shown as a badge, used by ad serving later)
`Campaign.state` is derived and not stored:

| state | when |
|---|---|
| `inactive` | status = INACTIVE (regardless of dates) |
| `scheduled` | ACTIVE and today < start_date |
| `live` | ACTIVE and start_date ≤ today ≤ end_date (`is_live`) |
| `ended` | ACTIVE and today > end_date |

### Ad preview
`templates/ads/_ad_card.html` renders an ad as a native feed card with the sponsor name (`AdvertiserProfile.company_name`, or the username if there's no profile), a **Sponsored** label, headline, body, optional image, and a "Learn more" link (`target="_blank" rel="sponsored noopener noreferrer"`). The portal uses it for previews, and the feed will use the **same partial**, so the preview matches what users will see.

### Query counts (locked by `ads/tests/test_queries.py`)
| Page | Queries |
|---|---|
| Dashboard | 4 (session, user, profile, campaigns with ad counts) |
| Campaign detail | 5 (session, user, campaign, ad units, profile) |

## Media uploads
- `MEDIA_ROOT = BASE_DIR / "media"`, `MEDIA_URL = "/media/"`. Post images go to `media/posts/YYYY/MM/`. Ad images go to `media/ads/YYYY/MM/`.
- `config/urls.py` serves media only when `DEBUG=True` (Django's approach for development). **Production needs object storage or a web server** (see [external-dependencies.md](external-dependencies.md)).
- Upload validation in `PostForm` and `AdUnitForm`: Pillow must be able to open the file as an image, and it must be at most **5 MB** (`core.validators.MAX_IMAGE_BYTES`).
- Tests redirect `MEDIA_ROOT` to a temporary directory (`posts.tests.utils.TempMediaMixin`).
- Deleting a post or ad unit does **not** delete its image file (known gap).

## Key flows
- **Signup:** each role has its own form (`accounts/forms.py`). The form sets the role on the server, so it can't be chosen via POST data. Advertiser signup creates the `User` and `AdvertiserProfile` inside one `transaction.atomic()`. The user is logged in after signup and redirected to `home`.
- **Login and logout:** Django's built-in `LoginView` and `LogoutView`. After login, `home` sends the user to their role's area.
- **Interactions (like, comment, follow, post):** a form POST with CSRF protection runs the action and then redirects (post/redirect/get). Like and follow are **toggles** built on `get_or_create`, and unique constraints prevent duplicates. Forms send `next=<current page>#post-<id>` so the user returns to the same place. `posts.utils.redirect_back` accepts `next` only if it points to the same host, which prevents open redirects.
- **Authors can't be spoofed:** `author`, `user`, and `follower` always come from `request.user`, never from form data.

## Templates
| Template | Purpose |
|---|---|
| `base.html` | Layout, Tailwind, flash messages, nav (`partials/nav.html`: Feed, People, My profile for regular users; Dashboard, New campaign for advertisers) |
| `posts/_post_card.html` | One post: author link, body, image, like toggle, comment previews, comment form |
| `posts/_follow_button.html` | Follow/Unfollow form (expects `target`, `following`) |
| `posts/_pagination.html` | Newer/Older links for any `page_obj` |
| `posts/feed.html`, `detail.html`, `profile.html`, `people.html` | Social pages |
| `ads/_ad_card.html` | Sponsored ad card (portal preview now, feed later) |
| `ads/_state_badge.html` | Live / Scheduled / Ended / Inactive badge |
| `ads/dashboard.html`, `campaign_form.html`, `campaign_detail.html`, `campaign_confirm_delete.html`, `adunit_form.html`, `adunit_confirm_delete.html` | Advertiser portal |
| `403.html`, `landing.html`, `registration/login.html`, `accounts/signup.html` | Other pages |
