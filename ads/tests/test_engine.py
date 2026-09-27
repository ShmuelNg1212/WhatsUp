import random
from datetime import timedelta

from django.test import SimpleTestCase, TestCase

from accounts.tests.helpers import make_advertiser, make_regular
from ads.engine import FEED_AD_INTERVAL, FeedItem, ad_slots, blend, record_impressions, select_feed_ads
from ads.models import AdImpression, Campaign

from .utils import make_ad_unit, make_campaign, today


def pattern(items):
    return "".join("A" if item.is_ad else "p" for item in items)


class BlendTests(SimpleTestCase):
    """The blender is pure: plain Python objects, no database."""

    def test_interval_is_four(self):
        self.assertEqual(FEED_AD_INTERVAL, 4)

    def test_ad_after_every_fourth_post_for_all_page_sizes(self):
        for n in range(0, 26):
            with self.subTest(posts=n):
                posts = [f"p{i}" for i in range(n)]
                ads = [f"a{i}" for i in range(ad_slots(n))]
                items = blend(posts, ads)
                expected = "".join("p" + ("A" if (i + 1) % 4 == 0 else "") for i in range(n))
                self.assertEqual(pattern(items), expected)
                self.assertEqual(sum(i.is_ad for i in items), n // 4)

    def test_full_page_of_twenty(self):
        items = blend(list(range(20)), list("abcde"))
        self.assertEqual(pattern(items), "ppppA" * 5)
        self.assertEqual([i.object for i in items if i.is_ad], list("abcde"))

    def test_posts_keep_their_order(self):
        items = blend(list(range(9)), ["x", "y"])
        self.assertEqual([i.object for i in items if i.is_post], list(range(9)))

    def test_no_ads_means_pure_organic(self):
        self.assertEqual(pattern(blend(list(range(12)), [])), "p" * 12)

    def test_fewer_ads_than_slots_leaves_slots_out(self):
        self.assertEqual(pattern(blend(list(range(12)), ["only"])), "ppppA" + "p" * 8)

    def test_extra_ads_are_ignored(self):
        self.assertEqual(pattern(blend(list(range(4)), list("abc"))), "ppppA")

    def test_fewer_than_four_posts_has_no_slots(self):
        self.assertEqual(ad_slots(3), 0)
        self.assertEqual(pattern(blend([1, 2, 3], ["a"])), "ppp")

    def test_custom_interval(self):
        self.assertEqual(pattern(blend(list(range(6)), list("abc"), every=2)), "ppAppAppA")

    def test_feed_item_flags(self):
        self.assertTrue(FeedItem("ad", None).is_ad)
        self.assertFalse(FeedItem("ad", None).is_post)
        self.assertTrue(FeedItem("post", None).is_post)


class SelectFeedAdsTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme", company_name="Acme Inc.")
        self.live = make_campaign(self.acme, "live")
        self.live_units = [make_ad_unit(self.live, f"live {i}") for i in range(3)]
        ended = make_campaign(
            self.acme, "ended", start_date=today() - timedelta(days=9), end_date=today() - timedelta(days=1)
        )
        make_ad_unit(ended, "ended ad")
        make_ad_unit(make_campaign(self.acme, "off", status=Campaign.Status.INACTIVE), "inactive ad")

    def test_zero_slots_runs_no_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(select_feed_ads(0), [])

    def test_only_servable_ads_are_chosen(self):
        for seed in range(20):
            chosen = select_feed_ads(3, rng=random.Random(seed))
            self.assertEqual(set(chosen), set(self.live_units))

    def test_distinct_before_repeating(self):
        chosen = select_feed_ads(3, rng=random.Random(1))
        self.assertEqual(len(set(chosen)), 3)

    def test_cycles_when_fewer_ads_than_slots(self):
        chosen = select_feed_ads(7, rng=random.Random(2))
        self.assertEqual(len(chosen), 7)
        self.assertEqual(chosen[:3], chosen[3:6])
        self.assertEqual(chosen[6], chosen[0])

    def test_single_ad_fills_every_slot(self):
        Campaign.objects.exclude(pk=self.live.pk).delete()
        for unit in self.live_units[1:]:
            unit.delete()
        self.assertEqual(select_feed_ads(5), [self.live_units[0]] * 5)

    def test_no_servable_ads(self):
        self.live.status = Campaign.Status.INACTIVE
        self.live.save()
        with self.assertNumQueries(1):
            self.assertEqual(select_feed_ads(5), [])

    def test_seeded_rng_is_deterministic(self):
        a = select_feed_ads(3, rng=random.Random(42))
        b = select_feed_ads(3, rng=random.Random(42))
        self.assertEqual(a, b)

    def test_rotation_varies_across_seeds(self):
        firsts = {select_feed_ads(1, rng=random.Random(seed))[0] for seed in range(30)}
        self.assertGreater(len(firsts), 1)

    def test_two_queries_and_cards_need_no_more(self):
        with self.assertNumQueries(2):
            chosen = select_feed_ads(5, rng=random.Random(0))
            names = [ad.sponsor_name for ad in chosen]
        self.assertEqual(set(names), {"Acme Inc."})


class RecordImpressionsTests(TestCase):
    def test_one_row_per_rendered_slot_in_one_query(self):
        unit = make_ad_unit(make_campaign(make_advertiser("acme")))
        alice = make_regular("alice")
        with self.assertNumQueries(1):
            record_impressions(alice, [unit, unit, unit])
        self.assertEqual(AdImpression.objects.filter(ad_unit=unit, user=alice).count(), 3)

    def test_nothing_to_record(self):
        with self.assertNumQueries(0):
            record_impressions(make_regular("alice"), [])
