"""
Feed query budget with ad injection. It is constant whatever the number of posts, ads, or advertisers.

    7  page has < 4 posts         (no ad slots → ad engine not consulted)
    8  >= 4 posts, no live ads    (+ eligible-ID lookup)
    10 >= 4 posts, live ads       (+ ID lookup, + one ad fetch with sponsor joined, + one impression INSERT)
    (each includes the social layout's 2 right-rail widget queries)
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Follow
from accounts.tests.helpers import make_advertiser, make_regular
from posts.tests.utils import TempMediaMixin, add_comment, add_like, make_image, make_post

from .utils import make_ad_unit, make_campaign

FEED = reverse("posts:feed")
FEED_QUERIES_NO_SLOTS = 7
FEED_QUERIES_NO_LIVE_ADS = 8
FEED_QUERIES_WITH_ADS = 10


class FeedQueryBudgetTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.viewer = make_regular("viewer")
        self.friends = [make_regular(f"friend{i}") for i in range(3)]
        for friend in self.friends:
            Follow.objects.create(follower=self.viewer, following=friend)
        self.client.force_login(self.viewer)

    def count(self):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(FEED).status_code, 200)
        return len(ctx.captured_queries)

    def add_posts(self, n):
        people = [self.viewer, *self.friends]
        for i in range(n):
            post = make_post(people[i % len(people)], f"p{i}")
            add_like(self.friends[0], post)
            add_comment(self.friends[1], post)

    def add_ads(self, advertisers, per_advertiser):
        for _ in range(advertisers):
            self.brand_count = getattr(self, "brand_count", 0) + 1
            advertiser = make_advertiser(f"brand{self.brand_count}")
            campaign = make_campaign(advertiser, "campaign")
            for _ in range(per_advertiser):
                make_ad_unit(campaign, image=make_image())

    def test_fewer_than_four_posts(self):
        self.add_ads(2, 2)
        self.add_posts(3)
        self.assertEqual(self.count(), FEED_QUERIES_NO_SLOTS)

    def test_no_live_ads(self):
        self.add_posts(4)
        small = self.count()
        self.add_posts(20)
        self.assertEqual(small, self.count())
        self.assertEqual(small, FEED_QUERIES_NO_LIVE_ADS)

    def test_with_ads_is_constant(self):
        self.add_ads(1, 1)
        self.add_posts(4)
        small = self.count()  # 1 slot
        self.add_ads(6, 3)
        self.add_posts(30)
        large = self.count()  # 5 slots, 6+ advertisers, images
        self.assertEqual(small, large, f"feed query count grew with ads ({small} → {large})")
        self.assertEqual(large, FEED_QUERIES_WITH_ADS)
