# Study: Ad Engine & Feed Injection (Slice 4)
- **Date:** 2026-09-27 18:04
- **Request:** Monetize the organic feed. Blend live `AdUnit`s into the regular user's feed at **one ad per 4 organic posts**, render them with a reusable "Sponsored" card that matches organic posts, record an `AdImpression` whenever an ad is shown, and send ad clicks through a tracking redirect (`/ads/click/<ad_id>/`) that records an `AdClick` and then 302-redirects to the ad's target URL.

## Intended Outcome
- A regular user's feed shows the usual organic posts, with a **Sponsored** ad after every 4th post (after posts 4, 8, 12, 16, and 20 on a full page of 20).
- Only ads from campaigns that are **live** (Active and within their dates) are ever shown.
- Every ad shown creates one `AdImpression` row (ad, user, timestamp).
- Clicking an ad goes to `/ads/click/<id>/`, which saves an `AdClick` (ad, user, timestamp) and redirects to the advertiser's site.
- Advertisers can see the impression and click counts (and click-through rate) for each ad in their portal.

**Acceptance criteria**
- [ ] With N organic posts on a page, the feed contains `N // 4` ads, each placed directly after a multiple of 4 posts. With fewer than 4 posts, no ads appear.
- [ ] Inactive, scheduled, and ended campaigns are never served.
- [ ] Impressions recorded = ads actually rendered, attributed to the viewer.
- [ ] The click endpoint saves one `AdClick` and returns **302** to the exact `target_url`. An unknown ad returns 404. Anonymous visitors are sent to login. Advertisers get 403, so they can't inflate clicks.
- [ ] Feed links on ads point to the click router, never directly to the target URL.
- [ ] The feed's SQL query count stays **constant** with ads injected.
- [ ] The full test suite passes.

## Current State
See [wiki/architecture.md](../wiki/architecture.md) and [wiki/data-models.md](../wiki/data-models.md).
- `posts.views.FeedView` → `posts.queries.feed_for(user)` → paginated at 20 per page, 5 queries per page (locked by `posts/tests/test_queries.py`).
- `ads.AdUnit` → `Campaign`, with the derived `Campaign.state`/`is_live` as a Python property. **No queryset equivalent exists yet.**
- `templates/ads/_ad_card.html` is already the "native" sponsored card, used for portal previews. Its "Learn more" link goes **directly** to `target_url`.
- **Design system note:** the request refers to a completed "Tailwind UI/UX Overhaul", but the repository has no such change. The last commit is `docs(wiki): sync after slice-3`, and templates are unchanged since Slice 3. This slice uses the design system that exists: Tailwind v4 plus the component classes in `base.html` and the `_post_card.html` look. If an overhaul lands later, the ad card is one partial to restyle.

## Part 1: Blending posts and ads without N+1 queries

### Options
| Option | How | Verdict |
|---|---|---|
| a. One SQL query with `UNION` of posts and ads | `.union()` needs identical column lists. That means dropping annotations and `select_related`, and ordering interleaved rows by a fake sort key. | **Rejected.** It fights the ORM, loses the tuned post query, and "every 4th item" isn't a SQL concept. |
| b. Loop over posts in the template and fetch an ad when `forloop.counter` is divisible by 4 | A template tag or model method per slot | **Rejected.** One query per ad slot (N+1), and a database side effect inside a template. |
| **c. Two bounded queries, merged in Python** | Page of posts (unchanged, tuned query) + a batch of the `k = len(posts) // 4` ads the page needs, fetched in **one** query with everything the card renders joined in. A pure function interleaves them into a list of typed feed items. | **Chosen.** Query count is fixed whatever the page size. The blending logic is pure Python, so it's easy to test exhaustively. The organic query is untouched. |

### Ad selection (which k ads)
Eligible ads are those whose **campaign is live**: `status = ACTIVE AND start_date ≤ today ≤ end_date`. This becomes a queryset method, `AdUnit.objects.servable(today)`. `Campaign.is_live` and the queryset must agree, and a test checks that they do.

| Option | Cost | Verdict |
|---|---|---|
| `order_by("?")[:k]` | Randomly sorts the **entire** eligible table on every feed load | Rejected; doesn't scale |
| **Fetch eligible IDs (`values_list("id")`), sample k in Python, then fetch those k rows with `select_related`** | 2 small queries. The ID list is a narrow, indexed scan. | **Chosen** |
| Budget-weighted or pacing-based selection | Needs spend tracking | Future (needs payments and spend accounting) |

- **Fewer eligible ads than slots:** fill as many slots as possible with **distinct** ads, then **cycle** through them again. This matches the "one ad per 4 posts" rule literally. With only one live ad in the system, that ad appears after every 4th post. **Assumption, flagged for the Gardener:** the alternative is "never repeat an ad on the same page", which would leave slots empty.
- **No eligible ads** → the feed is purely organic, with no extra queries after the ID lookup.
- **Fewer than 4 posts on the page** → zero slots, so ad queries are **skipped entirely**.
- Randomness goes through an injectable `random.Random` so tests are deterministic.
- **Scale note:** at tens of thousands of eligible ads, the ID list should be cached briefly (e.g. 60 s) or sampled in SQL. The selection function isolates this.

The ad fetch uses `select_related("campaign__advertiser__advertiser_profile")`, so the sponsor name on each card costs **zero** extra queries.

### Feed item representation (post vs. ad in the template)
```python
@dataclass(frozen=True)
class FeedItem:
    kind: Literal["post", "ad"]
    object: Post | AdUnit
    # template-friendly: item.is_post / item.is_ad
```
`blend(posts, ads, every=4) -> list[FeedItem]` is a **pure function** with no database access. The template branches on `{% if item.is_ad %}`. Both the view and the tests work with explicit types instead of guessing with `isinstance`. `posts` stays in the context too, so existing views and tests keep working.

### Expected query budget for the feed (fixed)
| # | Query | When |
|---|---|---|
| 1–2 | session, user | always |
| 3 | paginator COUNT | always |
| 4 | posts (with authors, counts, liked_by_me) | always |
| 5 | comment previews | always |
| 6 | eligible ad IDs | only if the page has ≥ 4 posts |
| 7 | chosen ads (+ campaign, advertiser, profile) | only if some IDs came back |
| 8 | impressions `bulk_create` (a single INSERT) | only if ads were shown |

The page has **5**, **6**, or **8** queries regardless of how many posts or ads it shows. `posts/tests/test_queries.py` will pin each case.

## Part 2: The safest way to track impressions

| Option | Accuracy | Robustness | Fraud resistance | Verdict |
|---|---|---|---|---|
| **A. Server-side, recorded by the view for ads it actually rendered** ("served impressions") | Counts what was sent to the user, not what scrolled into view | **High.** No JavaScript (the app currently has none), ad blockers can't suppress it, no extra requests, no CSRF surface | **High.** The server decides what counts, and clients can't fabricate impressions. | **Chosen** |
| B. Frontend ping (IntersectionObserver + `fetch`/`sendBeacon` to an endpoint) | Best "viewable" metric | Needs JavaScript, CSRF handling, and a new endpoint. Silently lost when blocked or when the tab closes. | **Low.** Any logged-in user can POST fake impressions for any ad. | Rejected for now. Can be added later as a separate "viewable impression" metric. |
| C. Tracking pixel (`<img src="/ads/impression/<id>">`) | Similar to A | GET with side effects. Cached and blocked by browsers and extensions. Lazy loading makes it unpredictable. | Low | Rejected |
| D. Template tag that writes to the database during rendering | Same as A | Database writes inside templates break "templates are side-effect free", can't be batched, and cause N+1 inserts | — | Rejected |

**How A is done safely:**
- The view **renders first, then records.** It builds the response (template rendered), and only then runs a single `AdImpression.objects.bulk_create([...])` for the ads in that response. If rendering fails, nothing is recorded. This avoids wrapping the request in a transaction.
- Impressions are recorded **only for GET requests from REGULAR_USERs** (the feed's existing gate), and **not for HEAD** requests, even though Django routes HEAD through `get()`.
- One row per rendered slot. If the same ad fills two slots on a page because of cycling, that's two impressions, since it really was shown twice.
- Refreshing the page counts again. That's the standard definition of a served impression. De-duplication and frequency capping are future work, and the `(user, created_at)` index supports them.
- **Known limitation:** this counts ads *served*, not ads *scrolled into view*. An ad at position 20 counts even if the user never scrolls that far. Documented in the wiki.

## Part 3: The click router

`GET /ads/click/<ad_id>/` → record an `AdClick(ad_unit, user, created_at)` → `302 Location: <ad.target_url>`.

- **Access:** REGULAR_USER only (same role gate as the feed). Anonymous → login. **Advertisers → 403** and nothing is recorded, so advertisers can't inflate their own or a competitor's clicks.
- **Portal previews link directly** to `target_url`, not through the router, so advertisers testing their own ad never create fake clicks. The card partial takes a `tracked` flag.
- **Ad lookup:** by ID across **all** ad units, not only live ones. A user who loaded the feed just before a campaign ended should still reach the site, and the click is still real. Unknown or deleted ID → 404.
- **Open redirect?** No. The destination is never taken from the request. It's the stored `target_url`, which the model validator already restricts to `http`/`https`. Django's `HttpResponseRedirect` refuses any other scheme as a second check.
- **Caching:** `never_cache` stops a browser or proxy from caching the 302 and skipping the tracking hop on later clicks.
- **GET with a side effect** is the industry standard for click redirects: links must be ordinary `<a href>` elements. Link prefetchers could create phantom clicks, which is an accepted limitation. `rel="sponsored noopener noreferrer"` and `target="_blank"` are kept.

## Part 4: Data model
`AdImpression` and `AdClick` share one shape, via an abstract base `AdEvent`:

| Field | Type | Why |
|---|---|---|
| `ad_unit` | FK → AdUnit, **CASCADE** | Deleting an ad deletes its stats. This follows the accepted Slice 3 rule "deleting is permanent". **Billing will need soft-delete or snapshots before real money**, which is noted as a risk. |
| `user` | FK → User, **SET_NULL**, null | If a user deletes their account, the advertiser's counts must not change retroactively. |
| `created_at` | DateTimeField, auto, indexed via composite indexes | |

Indexes: `(ad_unit, created_at)` for per-ad stats and time windows, and `(user, created_at)` for future frequency capping.

These are **append-only** telemetry: the admin is read-only (no add, change, or delete).

Plus an eligibility index on `Campaign(status, start_date, end_date)` for `servable()`.

## Part 5: UI
- `ads/_ad_card.html` (existing) gains a `tracked` mode. In the feed, `href` points to the click router. In the portal, it keeps the direct link. The header is changed to mirror `_post_card.html` (the same spacing and name treatment), with a clearer **Sponsored** tag: a pill with an icon, `aria-label="Sponsored content"`, and a subtle border tint so it's distinguishable at a glance while still looking native.
- A new `posts/_feed_item.html` dispatches on `item.is_ad` / `item.is_post` to the right card, so the feed loop stays a single `{% include %}`.
- **Portal stats (small addition):** the campaign detail page shows **Impressions / Clicks / CTR** under each ad preview. This lets the Gardener verify telemetry without the admin. It's a `Count(distinct)` annotation on the existing ad-units query, so still 5 queries.

## Exogenous Inputs
None. Everything is internal. (Payments and budget pacing remain future work, already listed.)

## Risks & Open Questions
**Product defaults assumed** (flagged at Rendezvous):
1. **Ads repeat on a page when there are fewer live ads than slots.** With one live ad, it appears after every 4th post.
2. **Uniform random choice** among live ads. There's no targeting, budget weighting, or pacing, and budgets are still not spent or enforced.
3. **Impressions are "served", not "viewed",** and refreshes count again. No frequency capping.
4. **Ads appear only on the main feed** (`/feed/`), not on profiles or post pages.
5. **Deleting an ad deletes its impression and click history.**
6. **Only regular users generate telemetry.** Advertiser clicks on the router are refused (403). Portal preview links bypass tracking.

**Technical risks**
- Serving the eligible-ID list scales linearly with the number of live ads, so it will need caching or SQL sampling at large scale (isolated in `ads/engine.py`).
- Recording impressions writes on every feed load. That's fine for SQLite development. In production at scale it would move to an async queue or batched writes.
- No "Tailwind UI/UX Overhaul" exists in the repo. See Current State.
