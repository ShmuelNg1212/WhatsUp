# Data Models

## Relationship overview
```
                        ┌──────────── Follow ────────────┐
                        │ follower ──►  User  ◄── following│   (asymmetric, many-to-many with itself)
                        └─────────────────────────────────┘
User 1 ──── 0..1 AdvertiserProfile      (only when role = ADVERTISER)
User 1 ──── *    Post                   (author)
User 1 ──── *    Like    * ──── 1 Post  (unique per user+post)
User 1 ──── *    Comment * ──── 1 Post
```
Every foreign key uses **CASCADE**. Deleting a user removes their profile, follows (in both directions), posts, likes, and comments. Deleting a post removes its likes and comments, but **not** its image file.

Only `REGULAR_USER`s take part in the social models. Views enforce this through role gating, and `Follow.clean()` enforces it for follows.

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
| posts | `0001_initial` | Post, Like, Comment, with constraints and indexes |
| posts | `0002_enforce_body_max_length` | Max-length validators on `body` fields |
