# Data Models

## Relationship overview
```
                        ┌──────────── Follow ────────────┐
                        │ follower ──►  User  ◄── following│   (asymmetric, many-to-many with itself)
                        └─────────────────────────────────┘
User 1 ──── 0..1 AdvertiserProfile      (only when role = ADVERTISER)
User 1 ──── *    Campaign 1 ──── * AdUnit   (advertiser; ad unit owner = campaign.advertiser)
AdUnit 1 ──── * AdImpression * ──── 0..1 User   (viewer; kept as NULL if the viewer is deleted)
AdUnit 1 ──── * AdClick      * ──── 0..1 User   (clicker; kept as NULL if the clicker is deleted)
User 1 ──── *    Post                   (author)
User 1 ──── *    Like    * ──── 1 Post  (unique per user+post)
User 1 ──── *    Comment * ──── 1 Post
```
Every foreign key uses **CASCADE**. Deleting a user removes their profile, follows (in both directions), posts, likes, comments, and campaigns. Deleting a post removes its likes and comments. Deleting a campaign removes its ad units, and deleting an ad unit removes its impressions and clicks. **Exception:** telemetry `user` is SET_NULL, so deleting a viewer keeps the advertiser's counts. Image files are **not** deleted from disk.

Only `REGULAR_USER`s take part in the social models. Views enforce this through role gating, and `Follow.clean()` enforces it for follows. Only `ADVERTISER`s own campaigns, enforced by portal gating, `Campaign.clean()`, and `limit_choices_to` in the admin.

---

## `accounts.User` (extends `AbstractUser`)
`AUTH_USER_MODEL = "accounts.User"`

| Field | Type | Notes |
|---|---|---|
| *(AbstractUser fields)* | | `username` (unique, login ID), `password`, `first_name`, `last_name`, `is_staff`, `is_active`, `is_superuser`, `date_joined`, `last_login` |
| `email` | EmailField | **Required** (`REQUIRED_FIELDS = ["email"]`) |
| `role` | CharField(20), indexed | `User.Role`: `REGULAR_USER` (default) or `ADVERTISER` |
| `following` | M2M → `self` **through `Follow`** | `symmetrical=False`, reverse accessor `followers` |

Constraints:
- `accounts_user_role_valid`: CHECK that `role` is one of the two values.
- `accounts_user_email_ci_unique`: UNIQUE on `LOWER(email)`, so emails are unique regardless of case.

Helpers: `user.is_regular_user`, `user.is_advertiser`, `user.following.all()`, `user.followers.count()`.

## `accounts.Follow`
An asymmetric edge in the social graph: `follower` sees `following`'s posts. No approval step and no follow-back is required.

| Field | Type | Notes |
|---|---|---|
| `follower` | FK → User | reverse accessor `following_edges` |
| `following` | FK → User | reverse accessor `follower_edges` |
| `created_at` | DateTimeField | Set automatically |

Constraints and indexes:
- `accounts_follow_unique_pair`: UNIQUE (follower, following), so a user can't follow someone twice. It also indexes lookups in the follower → following direction.
- `accounts_follow_no_self_follow`: CHECK follower ≠ following.
- `accounts_follow_reverse_idx`: INDEX (following, follower) for "who follows X".
- `clean()`: both sides must be `REGULAR_USER`.

Why an explicit through model instead of a plain M2M: it gives us `created_at`, our own named constraints (including blocking self-follows), and admin access, while keeping the easy `user.following` API. See [the study](../study/2026-09-27-1732-organic-mechanics.md).

## `ads.AdvertiserProfile`
| Field | Type | Notes |
|---|---|---|
| `user` | OneToOne → User | `related_name="advertiser_profile"` |
| `company_name` | CharField(200) | Required |
| `website` | URLField | Optional |
| `created_at` | DateTimeField | Set automatically |

Invariant: only `ADVERTISER` users have a profile. It is enforced by `clean()` and by atomic advertiser signup; the database can't enforce a rule across two tables.

## `ads.Campaign`
A budgeted campaign owned by exactly one advertiser.

| Field | Type | Notes |
|---|---|---|
| `advertiser` | FK → User | `related_name="campaigns"`, `limit_choices_to={"role": "ADVERTISER"}`. Set by the portal from `request.user`, never from a form. |
| `name` | CharField(120) | Unique per advertiser |
| `budget` | DecimalField(12, 2) | "Total budget (USD)". ≥ 0.01. **Stored only**: no money is charged yet. |
| `start_date`, `end_date` | DateField | end ≥ start |
| `status` | CharField(10) | `Campaign.Status`: `ACTIVE` / `INACTIVE` (default **INACTIVE**) |
| `created_at`, `updated_at` | DateTimeField | Set automatically |

Default ordering: `-created_at, -id`. `get_absolute_url()` → `/ads/campaigns/<pk>/`.

Constraints:
- `ads_campaign_unique_name_per_advertiser`: UNIQUE (advertiser, name). The form also checks this **case-insensitively**.
- `ads_campaign_budget_positive`: CHECK budget > 0.
- `ads_campaign_end_after_start`: CHECK end_date ≥ start_date.
- `ads_campaign_status_valid`: CHECK status IN ('ACTIVE', 'INACTIVE').
- `clean()`: the owner must have role `ADVERTISER`.

Derived (not stored): `state`, one of `live` / `scheduled` / `ended` / `inactive` (`Campaign.State`), and `is_live` (ACTIVE and start ≤ today ≤ end, in the server's time zone, UTC). Dashboard annotation: `ad_count`.

Manager `Campaign.objects` (`CampaignQuerySet`): `.live(today=None)` is the queryset form of `is_live`, and a test keeps the two in step.

Index `ads_campaign_serving_idx`: (status, start_date, end_date), used by ad serving.

## `ads.AdUnit`
One advertisement in a campaign. Its owner is **derived** (`ad_unit.advertiser` → `campaign.advertiser`) and never stored separately, so the two can't drift apart.

| Field | Type | Notes |
|---|---|---|
| `campaign` | FK → Campaign | `related_name="ad_units"`. Set by the portal from the URL after the ownership check. |
| `headline` | CharField(90) | Required |
| `body` | TextField | "Body text". Required, max **300** characters (model validator). |
| `image` | ImageField | Optional. Stored at `ads/%Y/%m/`. Max 5 MB (form check). |
| `target_url` | URLField(500) | Required. **http/https only** (`URLValidator(schemes=["http", "https"])`). The form adds `https://` when no scheme is given. |
| `created_at`, `updated_at` | DateTimeField | Set automatically |

Default ordering: `created_at, id`.
- `ads_adunit_headline_not_empty`, `ads_adunit_body_not_empty`: CHECK ≠ ''.
- `ads_adunit_campaign_time_idx`: INDEX (campaign, created_at).

Manager `AdUnit.objects` (`AdUnitQuerySet`): `.servable(today=None)` returns units whose campaign is live, the **only** source of feed ads.

Helpers: `ad_unit.advertiser` (= `campaign.advertiser`) and `ad_unit.sponsor_name` (company name, or the username). Load with `select_related("campaign__advertiser__advertiser_profile")` for zero queries. Portal annotations (not stored): `impression_count`, `click_count`, `ctr`.

## `ads.AdImpression` and `ads.AdClick` (telemetry)
The two share an abstract base, `ads.AdEvent`. Rows are **append-only** (read-only in the admin). Ordering: `-created_at, -id`.

| Field | Type | Notes |
|---|---|---|
| `ad_unit` | FK → AdUnit, **CASCADE** | Reverse accessors: `ad_unit.impressions` / `ad_unit.clicks` |
| `user` | FK → User, **SET_NULL**, nullable | The viewer or clicker. Reverse accessors: `user.ad_impressions` / `user.ad_clicks` |
| `created_at` | DateTimeField | Set automatically |

| Model | Meaning | Written by |
|---|---|---|
| `AdImpression` | The ad was **served** (rendered) in this user's feed, once per slot | `ads.engine.record_impressions` from `FeedView`, after a successful render |
| `AdClick` | The user clicked the ad | `ads.views.AdClickView` (`/ads/click/<id>/`), before the redirect |

Indexes (on each model): `(ad_unit, created_at)` for per-ad stats and time windows, and `(user, created_at)` for future frequency capping. Names: `ads_impression_ad_time_idx`, `ads_impression_user_time_idx`, `ads_click_ad_time_idx`, `ads_click_user_time_idx`.

**Note for billing:** because `ad_unit` is CASCADE, deleting an ad deletes its history. Real billing will need soft-delete or snapshots first.

## `posts.Post`
| Field | Type | Notes |
|---|---|---|
| `author` | FK → User | reverse accessor `posts` |
| `body` | TextField | Required, max **2,000** characters (enforced by a model validator) |
| `image` | ImageField | Optional. Stored at `posts/%Y/%m/` under `MEDIA_ROOT`. Max 5 MB (form check). |
| `created_at` | DateTimeField | Set automatically |

Default ordering: `-created_at, -id`. `get_absolute_url()` → `/posts/<id>/`.

Constraints and indexes:
- `posts_post_body_not_empty`: CHECK body ≠ ''.
- `posts_post_author_recent_idx`: INDEX (author, -created_at) for profile pages and the feed's author filter.
- `posts_post_recent_idx`: INDEX (-created_at) for ordering.

Annotations added by `posts.queries` (not stored): `like_count`, `comment_count`, `liked_by_me`, and `shown_comments` (a prefetched list).

## `posts.Like`
| Field | Type | Notes |
|---|---|---|
| `user` | FK → User | reverse accessor `likes` |
| `post` | FK → Post | reverse accessor `likes` |
| `created_at` | DateTimeField | Set automatically |

- `posts_like_once_per_user`: UNIQUE (user, post). A user can like a given post at most once. This also serves `liked_by_me` lookups.
- `posts_like_post_idx`: INDEX (post) for counts.
- Users can like their own posts.

## `posts.Comment`
| Field | Type | Notes |
|---|---|---|
| `post` | FK → Post | reverse accessor `comments` |
| `author` | FK → User | reverse accessor `comments` |
| `body` | TextField | Required, max **1,000** characters (enforced by a model validator) |
| `created_at` | DateTimeField | Set automatically |

Default ordering: `created_at, id` (oldest first, reading order).
- `posts_comment_body_not_empty`: CHECK body ≠ ''.
- `posts_comment_post_time_idx`: INDEX (post, created_at) for per-post comment lists and the sliced previews.

## Migrations
| App | Migration | Contents |
|---|---|---|
| accounts | `0001_initial` | User |
| accounts | `0002_follow_user_following_and_more` | Follow, `User.following`, follow constraints and index |
| ads | `0001_initial` | AdvertiserProfile |
| ads | `0002_campaign` | Campaign, with constraints |
| ads | `0003_adunit` | AdUnit, with constraints and index |
| ads | `0004_campaign_serving_index` | Campaign serving index |
| ads | `0005_ad_telemetry` | AdImpression, AdClick, with indexes |
| posts | `0001_initial` | Post, Like, Comment, with constraints and indexes |
| posts | `0002_enforce_body_max_length` | Max-length validators on `body` fields |
