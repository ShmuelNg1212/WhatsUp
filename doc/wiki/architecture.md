# Architecture

## Stack
| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Framework | Django 6.1.1 |
| Image handling | Pillow 12.3.0 (required by `ImageField`) |
| Database | SQLite (development) |
| Frontend | Server-rendered Django templates + Tailwind CSS v4 browser CDN (dev only; needs a compiled build before production). No JavaScript: every interaction is an HTML form POST or a plain link; menus use `<details>`. **Design system: [design-system.md](design-system.md)** (Inter, brand pink + sage neutrals, three layouts, `templates/components/`). |
| Auth | `django.contrib.auth` with a custom user model |
| Tests | Django's built-in test runner (`TestCase`) |

## Project layout
```
config/            project package: settings/{base,dev,test,prod}.py, urls.py, wsgi/asgi
accounts/          identity + social graph: User, Follow, signup/login/logout, role permissions, home router
posts/             the social area: Post, Like, Comment, feed/profile/people views, query builders
ads/               the advertiser portal: AdvertiserProfile, Campaign, AdUnit, ownership mixins, CRUD views
core/              plain package (not an app) with shared helpers: core/validators.py (image size)
*/templatetags/    UI-only helpers: accounts/templatetags/ui.py, posts/templatetags/social_widgets.py
templates/         layouts/ (public, social, portal) · components/ (shared UI) · errors/ · per-app folders (partials start with _)
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
| Logged in, role not allowed | 403 (`templates/403.html`, rendered inside the viewer's own layout) |
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
| `/ads/click/<ad_id>/` | `ads:click` | GET only (HEAD/POST → 405) | **Regular** (advertisers → 403). Records an `AdClick`, then 302 to the ad's `target_url`. Never cached. |
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

**Queries per page are fixed, whatever the amount of content.** Every social page renders the layout's right rail (*Who to follow*, *Trending*), which adds a constant 2 queries (`posts/templatetags/social_widgets.py`). `posts/tests/test_queries.py` and `ads/tests/test_feed_queries.py` lock these numbers:

| Page | Queries | Breakdown |
|---|---|---|
| Feed | 7 / 8 / 10 | 5 base (session, user, paginator count, posts with authors, counts and liked_by_me, comment previews). +1 eligible-ad lookup when the page has ≥ 4 posts. +1 ad fetch and +1 impression INSERT when live ads exist. See [Feed ad injection](#feed-ad-injection). +2 right-rail widgets. |
| Profile | 9 | session, user, profile user (with follow counts), paginator count, posts, comment previews, is-following check, +2 right-rail widgets |
| Post detail | 6 | session, user, post, all comments, +2 right-rail widgets |
| People | 6 | session, user, paginator count, people (with counts and followed_by_me), +2 right-rail widgets |

If any of these tests fails, a template or view has started running a query per item. Fix the query builder; don't change the expected numbers.

**Scaling notes:** `COUNT DISTINCT` over two joins is fine at this scale. The next steps would be subquery counts, then cached counters, then fan-out on write. The query builder isolates this, so views and templates won't change.

## Feed ad injection
Only the main feed (`/feed/`) carries ads. Profiles and post pages are purely organic.

### Algorithm (per feed page) in `ads/engine.py`
```
posts  = page of organic posts (feed_for, 20 per page)              2 queries (+3 fixed)
slots  = ad_slots(len(posts))        = len(posts) // 4             no queries
ads    = select_feed_ads(slots)                                      0 / 1 / 2 queries
items  = blend(posts, ads)           → [FeedItem]                   pure Python
render feed.html with feed_items
record_impressions(user, ads shown)  → 1 bulk INSERT                after a successful render
```

| Piece | Behavior |
|---|---|
| `FEED_AD_INTERVAL = 4` | One ad directly **after every 4th organic post**: positions 5, 10, 15, … in the blended list. A full page has 20 posts + 5 ads. **Fewer than 4 posts → no ads, and the ad engine isn't consulted.** |
| `blend(posts, ads, every=4)` | Pure function. Returns a list of `FeedItem(kind="post"\|"ad", object)` with `is_post`/`is_ad` flags. Posts keep their order. If there are fewer ads than slots, the missing slots are left out. Extra ads are ignored. |
| `select_feed_ads(count, rng=None, today=None)` | 1) `AdUnit.objects.servable(today).values_list("id")` → 2) `rng.sample(...)` in Python → 3) **one** `in_bulk` fetch with `select_related("campaign__advertiser__advertiser_profile")`, so sponsor names cost no queries. Distinct ads come first, then the selection **cycles** if there are fewer servable ads than slots (one live ad fills every slot). Uniform random choice, with no targeting or budget weighting. |
| Eligibility (`servable`) | Campaign `status = ACTIVE` and `start_date ≤ today ≤ end_date` (server time zone, UTC). Matches `Campaign.is_live`, and a test enforces that. Served by the index `ads_campaign_serving_idx`. |
| `record_impressions(user, ads)` | One `AdImpression` per rendered ad slot (a repeated ad counts once per slot), in one INSERT. |

**Why this design:** posts and ads come from two bounded queries merged in Python, so the tuned organic query is untouched and the query count is fixed. A SQL `UNION` or a per-slot template lookup (N+1) were rejected. The details and alternatives are in the [Slice 4 study](../study/2026-09-27-1804-ad-engine-injection.md).

**Scaling notes:** the eligible-ID list grows with the number of live ads. At tens of thousands of ads, cache it briefly or sample in SQL (only `select_feed_ads` changes). Impression writes happen on every feed load; at scale, batch them or send them to a queue.

### Rendering
- `FeedView.render_feed()` passes `feed_items` (and `posts`, for compatibility) to `posts/feed.html`.
- `posts/_feed_item.html` dispatches on `item.is_ad` → `ads/_ad_card.html` with `tracked=True`, or on `item.is_post` → `posts/_post_card.html`.
- `ads/_ad_card.html` mirrors the post card's layout (see [design-system.md](design-system.md#card-anatomy-post-and-ad-must-stay-in-step)), with a Tea Green ring and a **✦ SPONSORED** pill (`data-testid="sponsored-tag"`, `aria-label="Sponsored content from …"`). The headline, image, and "Learn more ↗" button all link to the same place:
  - `tracked=True` (feed) → `/ads/click/<id>/`
  - not tracked (portal preview) → `target_url` directly, **so previews never generate telemetry**

## Telemetry pipeline
| Event | Recorded by | When | Who |
|---|---|---|---|
| `AdImpression` | `FeedView` via `record_impressions` | **After** the feed renders successfully: GET requests and invalid-post re-renders. **Not HEAD**, and nothing if rendering fails. | The viewing regular user |
| `AdClick` | `AdClickView` (`/ads/click/<id>/`) | On each GET, **before** the 302 | The clicking regular user |

Definitions and guarantees:
- **Served impressions, recorded on the server.** Counts ads sent in a rendered page, not ads scrolled into view. Refreshing counts again. There's no de-duplication or frequency cap yet; the `(user, created_at)` index is ready for that. Clients can't fabricate impressions because there's no impression endpoint.
- **Clicks** go through the router. It looks the ad up by ID (any ad, even if the campaign has since ended; an unknown ID → 404), records the click, then redirects to the **stored, validated** `target_url` (http/https only), so it is not an open redirect. The response is `never_cache`. Anonymous visitors → login. **Advertisers → 403**, so they can't inflate clicks. HEAD and POST → 405.
- Telemetry is **append-only**. The admin pages for Ad impressions and Ad clicks are read-only (no add, change, or delete).
- **Reporting:** the campaign detail page annotates each ad unit with `impression_count`, `click_count` (`COUNT DISTINCT`, in the same query), and `ctr` (clicks ÷ impressions × 100, or "—" with no impressions). The page is still 5 queries.

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
`templates/ads/_ad_card.html` is the **same partial the feed uses**, so previews are exactly what users see. In the portal it's rendered untracked: links go straight to `target_url` and nothing is recorded. The sponsor name is `AdUnit.sponsor_name` (`AdvertiserProfile.company_name`, or the username if there's no profile). Links use `target="_blank" rel="sponsored noopener noreferrer"`. Under each preview the campaign page shows **Impressions / Clicks / CTR**.

### Query counts (locked by `ads/tests/test_queries.py`)
| Page | Queries |
|---|---|
| Dashboard | 4 (session, user, profile, campaigns with ad counts) |
| Campaign detail | 5 (session, user, campaign, ad units with impression and click counts, profile) |

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
The visual conventions, tokens, components, and layout rules are in **[design-system.md](design-system.md)**. Structure:

| Path | Purpose |
|---|---|
| `base.html` | Document shell: Inter, Tailwind CDN, `@theme` tokens, `@layer components`. Nothing else. |
| `layouts/public.html` · `social.html` · `portal.html` | Page shells per audience. Every page extends exactly one. `layouts/_portal_nav.html` is shared by the portal sidebar and the mobile menu. |
| `components/*.html` | Shared UI: icon, avatar, button, badge, form, form_field, messages, empty_state, page_header, metric_card, pagination, follow_button, logo |
| `403.html`, `404.html` → `errors/40x_page.html` | Error pages in the viewer's layout (`ui|error_layout`) |
| `landing.html`, `registration/login.html`, `accounts/signup.html` | Public pages |
| `posts/feed.html`, `detail.html`, `profile.html`, `people.html` | Social pages |
| `posts/_post_card.html`, `_comment.html`, `_composer.html`, `_feed_item.html`, `widgets/who_to_follow.html`, `widgets/trending.html` | Social partials. `_feed_item` dispatches a `FeedItem` to the post or ad card. |
| `ads/_ad_card.html` | Sponsored ad card: feed (`tracked=True`, links via the click router) and portal preview (direct links) |
| `ads/dashboard.html`, `campaign_detail.html`, `campaign_form.html`, `adunit_form.html`, `*_confirm_delete.html` | Advertiser portal pages. The delete pages extend `ads/_confirm_delete_base.html`. |
| `ads/_campaign_row.html`, `_ad_stats.html`, `_state_badge.html` | Portal partials |
