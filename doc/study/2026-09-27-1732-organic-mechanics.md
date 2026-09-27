# Study: Organic Social Mechanics (Slice 2)
- **Date:** 2026-09-27 17:32
- **Request:** Build the full experience for a `REGULAR_USER`: an asymmetric follow system with profile pages, posts with text and an optional image (local media uploads), likes (one per user per post), comments, and a reverse-chronological feed of your own posts plus posts from people you follow. Feed queries must avoid N+1 problems.

## Intended Outcome
A regular user can:
- Write a post (text, optionally with an image) and see it at the top of their feed immediately.
- Find other users, open their profile, and **Follow** or **Unfollow** them with one click. Follower and following counts update.
- See a feed containing **only** their own posts and posts from people they follow, newest first.
- **Like** or **unlike** any post they can see (at most one like per post) and see the like count.
- **Comment** on posts and read the comments.
- Do all of this from the feed and from profile pages.

**Acceptance criteria**
- [ ] After following user B, B's posts appear in A's feed. After unfollowing, they disappear. Posts from users A doesn't follow never appear.
- [ ] The feed is newest-first and paginated.
- [ ] Liking twice does not create a second like. The database rejects a duplicate like.
- [ ] A user cannot follow themselves or follow someone twice. The database rejects both.
- [ ] An uploaded image is saved under `media/` and shown in the feed while the dev server runs.
- [ ] The feed and profile pages run a **fixed number of SQL queries** no matter how many posts, likes, or comments are shown. This is proven by `assertNumQueries` tests.
- [ ] Advertisers still get 403 on every social page. Anonymous visitors are redirected to login.
- [ ] The full test suite passes.

## Current State
See [wiki/architecture.md](../wiki/architecture.md) and [wiki/data-models.md](../wiki/data-models.md).
- `accounts.User` has a `role` field. Areas are exclusive: advertisers cannot use the social area.
- `posts` app: only a placeholder `FeedView` (`RoleRequiredMixin`, `REGULAR_USER`) at `/feed/`.
- No media settings. No image library installed.

## Data Model Analysis

### Follow: M2M vs. explicit model
| Option | Pros | Cons |
|---|---|---|
| A. `ManyToManyField("self", symmetrical=False)` with an auto-generated join table | Least code | Nowhere to put `created_at`. Can't declare our own constraints, such as blocking self-follows. The join table is hidden. |
| B. Explicit `Follow` model (two FKs to User) only | Full control over fields, constraints, and admin | Queries through `Follow.objects` are more verbose |
| **C. Explicit `Follow` model + `User.following = ManyToManyField("self", through=Follow, symmetrical=False, related_name="followers")`** | Everything B offers, **plus** the easy `user.following.all()` / `user.followers.count()` API. This is the pattern Django documents. | The M2M declaration lives on `User`, so it needs a migration on `accounts` |

**Recommendation: C.** `Follow(follower → User, following → User, created_at)` with:
- `UniqueConstraint(follower, following)`: no duplicate follows
- `CheckConstraint(follower ≠ following)`: no self-follows
- An index on `(following, follower)` for the reverse direction ("who follows X"). The unique constraint already indexes the forward direction.

It lives in **`accounts`** because it is a relationship between users. The `posts` app depends on `accounts`, never the other way round.

**Asymmetric:** a Follow row means "follower sees following's posts". No approval step and no follow-back is required.

### Likes: M2M vs. explicit model
| Option | Pros | Cons |
|---|---|---|
| `Post.likers = ManyToManyField(User)` with an auto table | Little code, and Django adds a unique (post, user) constraint automatically | No `created_at`. The table is hidden. |
| **Explicit `Like(user FK, post FK, created_at)`** | You asked for a `Like` model. Explicit `UniqueConstraint(user, post)`. Timestamped, which future "trending" features or advertiser analytics will want. | Slightly more code |

**Recommendation: explicit `Like` model** with `UniqueConstraint(user, post)`. The unique index covers "did I like this post?" lookups, and an index on `post` covers counts.

### Comments: always a plain FK model
A comment has its own content and lifecycle, so it is an entity, not a link between two things. `Comment(post FK, author FK, body, created_at)`, ordered oldest-first within a post. An index on `(post, created_at)` serves "comments for this post in order".

### Post
`Post(author FK → User, body TextField(max_length=2000), image ImageField(blank=True), created_at)`:
- `CheckConstraint`: `body` cannot be empty, since text is the core content and the image is optional.
- An index on `(author, -created_at)` serves both the profile page and the feed's "authors I follow, newest first" query.
- Images are stored at `upload_to="posts/%Y/%m/"`. The form limits the size to **5 MB**. Pillow checks that the file really is an image.

### Deletion behavior
All foreign keys use `CASCADE`: deleting a user deletes their posts, likes, comments, and follows, and deleting a post deletes its likes and comments. **Deleted posts do not delete their image files from disk.** Cleaning up media files is deferred, which is fine for local development.

### Author role invariant
Only `REGULAR_USER`s write posts, like, comment, or follow, because advertisers are blocked from the whole social area. This is enforced by `RoleRequiredMixin` on every social view, the same approach as Slice 1. Follow targets must also be regular users: advertiser accounts have no public profile (404) and cannot be followed. `Follow.clean()` enforces this as a second check.

## Feed Query Strategy

A naive template loop runs about **1 + 4N queries** for N posts (author, like count, "did I like it", comments, and each comment's author). The plan instead uses a **fixed number of queries**:

```python
following_ids = Follow.objects.filter(follower=user).values("following_id")   # subquery, not a list

Post.objects
    .filter(Q(author=user) | Q(author_id__in=following_ids))                     # 1 SQL query with a subquery
    .select_related("author")                                                    # author joined in, no per-post query
    .annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("comments", distinct=True),
        liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=user)),
    )
    .prefetch_related(Prefetch(
        "comments",
        queryset=Comment.objects.select_related("author").order_by("-created_at")[:3]   # sliced prefetch
        ..., to_attr="recent_comments"))
    .order_by("-created_at", "-id")                                              # "-id" breaks timestamp ties
```

- **`select_related("author")`:** each post's author comes from a JOIN in the same query.
- **Counts via `annotate`:** these are computed in SQL. `distinct=True` stops the two joins from multiplying each other's counts. At larger scale they can become `Subquery` counts or cached counters. This is noted, but premature to do now.
- **`liked_by_me` via `Exists`:** a correlated subquery, so there is no per-post query and no loading of every like.
- **Sliced `Prefetch`** (supported since Django 4.2, using window functions, and SQLite 3.53 supports them): loads only the **latest 3 comments per post** in one extra query, with authors joined in. The feed shows "View all N comments", which links to a post page with every comment.
- **Pagination:** Django's `Paginator` at 20 posts per page adds one `COUNT` query.

Expected total per feed page, whatever the number of posts: session + user + count + posts + comments prefetch, a small constant (about 5). This will be pinned by `assertNumQueries` tests with 1 post and with 10 or more posts, each with likes and comments.

The same queryset builder (`posts/queries.py → annotated_posts(viewer)`) is used by the feed, profile, and post pages, so they all get the same optimization.

**Why not fan-out-on-write (precomputed per-user feed tables)?** That is the standard approach at very large scale, but it is premature here. Fan-out-on-read with indexed queries is correct and fast enough for this phase. The query builder isolates it, so swapping strategies later won't touch views or templates. **Sponsored ads (Slice 3) will be merged into the feed at the view layer, and this design leaves room for that.**

## Interaction Design
- Server-rendered HTML forms that **POST**, with CSRF protection and no JavaScript. This is Django's default approach.
- After an action, the user is redirected back to the page they came from. The `next` value is checked with `url_has_allowed_host_and_scheme` to prevent open redirects.
- Like and Follow are **toggles** (one endpoint each, POST only). Toggling is idempotent in the sense that a double submit cannot create duplicates, thanks to `get_or_create` plus the unique constraints.

### Routes (all `REGULAR_USER` only)
| Path | Purpose |
|---|---|
| `/feed/` | Feed + "new post" form (GET list, POST create) |
| `/posts/<id>/` | Single post with all comments + comment form |
| `/posts/<id>/like/` | POST: toggle like |
| `/posts/<id>/comments/` | POST: add comment |
| `/u/<username>/` | Profile: posts, follower/following counts, Follow/Unfollow |
| `/u/<username>/follow/` | POST: toggle follow |
| `/people/` | **Discover people**: list of other regular users with Follow buttons |

`/people/` goes beyond the literal request. Without it, a new user has no way to **find** anyone to follow except typing URLs by hand, so the feature couldn't be tested from the outside.

## Media Configuration
- `MEDIA_URL = "/media/"`, `MEDIA_ROOT = BASE_DIR / "media"` (already gitignored).
- In development, `config/urls.py` serves media with `django.conf.urls.static.static()` **only when `DEBUG=True`**. This is Django's documented approach for development. Production will need object storage or a web server (listed as a future external input).
- Tests override `MEDIA_ROOT` to a temporary directory so test uploads never pollute `media/`.

## Options Considered for App Placement
| Option | Verdict |
|---|---|
| New `social` app for Follow/Like/Comment | Rejected. Likes and comments are tied to `Post`, and splitting them adds imports across apps with no benefit. |
| **`Follow` in `accounts`; `Post`/`Like`/`Comment` + all social views in `posts`** | **Chosen.** Dependencies point one way: `posts → accounts`. |

## Exogenous Inputs
| Input | Why needed | Status | Owner |
|---|---|---|---|
| **Pillow** (PyPI) | Required by Django's `ImageField` | **verified**: 12.3.0 has a Python 3.14 macOS arm64 wheel | Vine |
| Production media storage (S3/GCS/R2, or a web server) | Serving uploads outside `DEBUG` | needed before deploy | Gardener |

Nothing blocks this slice.

## Risks & Open Questions
**Product defaults assumed** (flagged at Rendezvous):
1. **All regular-user profiles and posts are public** to every logged-in regular user. There are no private accounts or blocking.
2. **Advertisers cannot be followed** and have no public profile. This follows from Slice 1's "advertisers are business-only" default.
3. **No editing or deleting** of posts or comments in this slice. This was not requested and is an easy follow-up.
4. **The feed shows the latest 3 comments per post**. The rest are on the post page.
5. **Maximum lengths:** post 2,000 characters, comment 1,000 characters, image 5 MB.

**Technical risks**
- `Count(..., distinct=True)` over two joins is fine at this scale but grows as rows × likes × comments. It can be moved to subqueries later without changing the API.
- Media files outlive deleted posts, which is acceptable for development.
