"""
The feed ad engine: which ads to show, where to put them, and recording that they were shown.

Pipeline for one feed page (see doc/wiki/architecture.md, "Feed ad injection"):
    posts  = one page of organic posts             (posts.queries.feed_for)
    ads    = select_feed_ads(ad_slots(len(posts))) (2 queries, only if slots > 0)
    items  = blend(posts, ads)                     (pure Python, no queries)
    ...render...
    record_impressions(user, ads)                  (1 INSERT, after rendering)
"""

import random
from dataclasses import dataclass
from itertools import cycle, islice
from typing import Any, Literal

from .models import AdImpression, AdUnit

FEED_AD_INTERVAL = 4  # one ad after every 4 organic posts


@dataclass(frozen=True)
class FeedItem:
    kind: Literal["post", "ad"]
    object: Any

    @property
    def is_post(self):
        return self.kind == "post"

    @property
    def is_ad(self):
        return self.kind == "ad"


def ad_slots(post_count, every=FEED_AD_INTERVAL):
    """How many ads a page with `post_count` organic posts carries."""
    return post_count // every


def blend(posts, ads, every=FEED_AD_INTERVAL):
    """
    Interleave `ads` into `posts`: one ad directly after every `every`-th post,
    in the order given. Leftover ads are ignored; missing ads leave the slot out.
    Pure function: no database access.
    """
    items = []
    ads = iter(ads)
    for position, post in enumerate(posts, start=1):
        items.append(FeedItem("post", post))
        if position % every == 0:
            ad = next(ads, None)
            if ad is not None:
                items.append(FeedItem("ad", ad))
    return items


def select_feed_ads(count, rng=None, today=None):
    """
    Choose `count` servable ads for one page, with everything the card needs loaded.

    Distinct ads first (random order); if there are fewer servable ads than
    slots, cycle through them again so every slot is filled.
    Queries: 0 if count == 0; 1 if nothing is servable; otherwise 2.
    """
    if count <= 0:
        return []
    rng = rng or random.Random()
    ids = list(AdUnit.objects.servable(today).values_list("id", flat=True))
    if not ids:
        return []
    chosen_ids = rng.sample(ids, min(count, len(ids)))
    by_id = AdUnit.objects.select_related("campaign__advertiser__advertiser_profile").in_bulk(
        chosen_ids
    )
    distinct = [by_id[i] for i in chosen_ids if i in by_id]
    return list(islice(cycle(distinct), count)) if distinct else []


def record_impressions(user, ads):
    """One AdImpression per rendered ad slot, in a single INSERT."""
    if ads:
        AdImpression.objects.bulk_create([AdImpression(ad_unit=ad, user=user) for ad in ads])
