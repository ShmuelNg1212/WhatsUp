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
ads/               the advertiser area: AdvertiserProfile, dashboard
templates/         all templates, grouped by app; posts/_*.html are reusable partials
media/             user uploads (gitignored)
doc/               study/ (decisions), plan/ (checklists), wiki/ (this)
```
Each app keeps its tests in `<app>/tests/`.

**App dependencies point one way:** `posts → accounts` and `ads → accounts`. `accounts` imports `ads` only in the advertiser signup form.

## Roles and access control
Every account is an `accounts.User` with a `role`: `REGULAR_USER` or `ADVERTISER`. The areas are **exclusive**:
- The **social area** (feed, posts, profiles, people, likes, comments, follows) is for `REGULAR_USER` only.
- The **advertiser area** (`/ads/`) is for `ADVERTISER` only. Advertisers have no profile page and cannot be followed.

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
| `/media/<path>` | — | GET | Anyone; **served only when `DEBUG=True`** |
| `/admin/` | Django admin | — | Staff |

Toggle and create endpoints reject GET with 405.

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

**Scaling notes:** `COUNT DISTINCT` over two joins is fine at this scale. The next steps would be subquery counts, then cached counters, then fan-out on write. The query builder isolates this, so views and templates won't change. Sponsored ads (next slice) will be merged into the feed at the view layer.

## Media uploads
- `MEDIA_ROOT = BASE_DIR / "media"`, `MEDIA_URL = "/media/"`. Post images go to `media/posts/YYYY/MM/`.
- `config/urls.py` serves media only when `DEBUG=True` (Django's approach for development). **Production needs object storage or a web server** (see [external-dependencies.md](external-dependencies.md)).
- Upload validation in `PostForm`: Pillow must be able to open the file as an image, and it must be at most **5 MB** (`posts.forms.MAX_IMAGE_BYTES`).
- Tests redirect `MEDIA_ROOT` to a temporary directory (`posts.tests.utils.TempMediaMixin`).
- Deleting a post does **not** delete its image file.

## Key flows
- **Signup:** each role has its own form (`accounts/forms.py`). The form sets the role on the server, so it can't be chosen via POST data. Advertiser signup creates the `User` and `AdvertiserProfile` inside one `transaction.atomic()`. The user is logged in after signup and redirected to `home`.
- **Login and logout:** Django's built-in `LoginView` and `LogoutView`. After login, `home` sends the user to their role's area.
- **Interactions (like, comment, follow, post):** a form POST with CSRF protection runs the action and then redirects (post/redirect/get). Like and follow are **toggles** built on `get_or_create`, and unique constraints prevent duplicates. Forms send `next=<current page>#post-<id>` so the user returns to the same place. `posts.utils.redirect_back` accepts `next` only if it points to the same host, which prevents open redirects.
- **Authors can't be spoofed:** `author`, `user`, and `follower` always come from `request.user`, never from form data.

## Templates
| Template | Purpose |
|---|---|
| `base.html` | Layout, Tailwind, flash messages, nav (`partials/nav.html`: Feed, People, My profile for regular users) |
| `posts/_post_card.html` | One post: author link, body, image, like toggle, comment previews, comment form |
| `posts/_follow_button.html` | Follow/Unfollow form (expects `target`, `following`) |
| `posts/_pagination.html` | Newer/Older links for any `page_obj` |
| `posts/feed.html`, `detail.html`, `profile.html`, `people.html` | Social pages |
| `403.html`, `landing.html`, `registration/login.html`, `accounts/signup.html`, `ads/dashboard.html` | Other pages |
