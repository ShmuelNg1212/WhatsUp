from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import Follow, User
from accounts.tests.helpers import make_advertiser, make_regular
from ads.models import AdClick, AdImpression, Campaign
from posts.tests.utils import make_post

from .utils import make_ad_unit, make_campaign, today

FEED = reverse("posts:feed")


def pattern(response):
    return "".join("A" if item.is_ad else "p" for item in response.context["feed_items"])


class FeedInjectionTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.acme = make_advertiser("acme", company_name="Acme Inc.")
        self.campaign = make_campaign(self.acme, "Launch")
        self.ad = make_ad_unit(self.campaign, "Anvils 50% off", target_url="https://acme.example/sale")
        self.client.force_login(self.alice)

    def make_posts(self, n, author=None):
        for i in range(n):
            make_post(author or self.bob, f"post {i}")

    def test_one_ad_after_every_four_posts(self):
        self.make_posts(10)
        self.assertEqual(pattern(self.client.get(FEED)), "ppppAppppApp")

    def test_full_page_has_five_ads(self):
        self.make_posts(20)
        response = self.client.get(FEED)
        self.assertEqual(pattern(response), "ppppA" * 5)

    def test_second_page_also_gets_ads(self):
        self.make_posts(28)
        self.assertEqual(pattern(self.client.get(FEED, {"page": 2})), "ppppAppppA")

    def test_no_ads_with_fewer_than_four_posts(self):
        self.make_posts(3)
        response = self.client.get(FEED)
        self.assertEqual(pattern(response), "ppp")
        self.assertFalse(AdImpression.objects.exists())

    def test_own_posts_count_toward_the_interval(self):
        self.make_posts(2)
        self.make_posts(2, author=self.alice)
        self.assertEqual(pattern(self.client.get(FEED)), "ppppA")

    def test_organic_posts_keep_order_and_membership(self):
        self.make_posts(8)
        make_post(make_regular("stranger"), "not followed")
        response = self.client.get(FEED)
        bodies = [i.object.body for i in response.context["feed_items"] if i.is_post]
        self.assertEqual(bodies, [f"post {i}" for i in range(7, -1, -1)])
        self.assertEqual(list(response.context["posts"]), [i.object for i in response.context["feed_items"] if i.is_post])

    def test_ended_inactive_and_scheduled_campaigns_are_never_served(self):
        self.campaign.status = Campaign.Status.INACTIVE
        self.campaign.save()
        d = timedelta(days=1)
        make_ad_unit(make_campaign(self.acme, "ended", start_date=today() - 9 * d, end_date=today() - d))
        make_ad_unit(make_campaign(self.acme, "soon", start_date=today() + d, end_date=today() + 9 * d))
        self.make_posts(12)
        self.assertEqual(pattern(self.client.get(FEED)), "p" * 12)
        self.assertFalse(AdImpression.objects.exists())

    def test_ad_card_is_marked_sponsored_and_links_through_router(self):
        self.make_posts(4)
        response = self.client.get(FEED)
        click_url = reverse("ads:click", args=[self.ad.pk])
        self.assertContains(response, 'data-testid="sponsored-tag"')
        self.assertContains(response, "Sponsored")
        self.assertContains(response, "Acme Inc.")
        self.assertContains(response, "Anvils 50% off")
        self.assertContains(response, f'href="{click_url}"')
        self.assertNotContains(response, 'href="https://acme.example/sale"')
        self.assertTemplateUsed(response, "posts/_feed_item.html")
        self.assertTemplateUsed(response, "ads/_ad_card.html")

    def test_portal_preview_links_directly_and_is_not_tracked(self):
        self.client.force_login(self.acme)
        response = self.client.get(self.campaign.get_absolute_url())
        self.assertContains(response, 'href="https://acme.example/sale"')
        self.assertNotContains(response, reverse("ads:click", args=[self.ad.pk]))
        self.assertFalse(AdImpression.objects.exists())

    def test_empty_state_still_shows(self):
        self.assertContains(self.client.get(FEED), "Your feed is empty.")


class ImpressionRecordingTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.acme = make_advertiser("acme")
        self.ads = [make_ad_unit(make_campaign(self.acme, f"c{i}"), f"ad {i}") for i in range(2)]
        self.client.force_login(self.alice)
        for i in range(10):
            make_post(self.alice, f"post {i}")

    def test_one_impression_per_rendered_ad_for_the_viewer(self):
        response = self.client.get(FEED)
        shown = [i.object for i in response.context["feed_items"] if i.is_ad]
        self.assertEqual(len(shown), 2)
        impressions = AdImpression.objects.all()
        self.assertEqual(impressions.count(), 2)
        self.assertCountEqual([i.ad_unit for i in impressions], shown)
        self.assertTrue(all(i.user == self.alice for i in impressions))

    def test_repeated_ad_counts_each_slot(self):
        self.ads[1].campaign.delete()
        self.client.get(FEED)
        self.assertEqual(AdImpression.objects.filter(ad_unit=self.ads[0]).count(), 2)

    def test_each_page_load_counts(self):
        self.client.get(FEED)
        self.client.get(FEED)
        self.assertEqual(AdImpression.objects.count(), 4)

    def test_head_request_records_nothing(self):
        self.assertEqual(self.client.head(FEED).status_code, 200)
        self.assertFalse(AdImpression.objects.exists())

    def test_invalid_post_rerender_counts_shown_ads(self):
        response = self.client.post(FEED, {"body": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AdImpression.objects.count(), 2)

    def test_nothing_recorded_if_rendering_fails(self):
        with mock.patch("posts.views.render", side_effect=RuntimeError("template blew up")):
            with self.assertRaises(RuntimeError):
                self.client.get(FEED)
        self.assertFalse(AdImpression.objects.exists())

    def test_advertisers_and_anonymous_generate_no_impressions(self):
        self.client.force_login(self.acme)
        self.assertEqual(self.client.get(FEED).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(FEED).status_code, 302)
        self.assertFalse(AdImpression.objects.exists())


class ClickRouterTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.acme = make_advertiser("acme")
        self.ad = make_ad_unit(make_campaign(self.acme), target_url="https://acme.example/sale?utm=feed")
        self.url = reverse("ads:click", args=[self.ad.pk])

    def test_url_shape(self):
        self.assertEqual(self.url, f"/ads/click/{self.ad.pk}/")

    def test_records_click_and_redirects_to_target(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://acme.example/sale?utm=feed")
        click = AdClick.objects.get()
        self.assertEqual((click.ad_unit, click.user), (self.ad, self.alice))

    def test_every_click_is_recorded(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(AdClick.objects.count(), 2)

    def test_response_is_not_cacheable(self):
        self.client.force_login(self.alice)
        cache_control = self.client.get(self.url)["Cache-Control"]
        for directive in ("no-cache", "no-store", "must-revalidate"):
            self.assertIn(directive, cache_control)

    def test_still_redirects_after_campaign_ends(self):
        self.ad.campaign.status = Campaign.Status.INACTIVE
        self.ad.campaign.save()
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url)["Location"], self.ad.target_url)
        self.assertEqual(AdClick.objects.count(), 1)

    def test_unknown_ad_is_404_and_records_nothing(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("ads:click", args=[9999])).status_code, 404)
        self.assertFalse(AdClick.objects.exists())

    def test_anonymous_is_sent_to_login_and_nothing_recorded(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}", fetch_redirect_response=False)
        self.assertFalse(AdClick.objects.exists())

    def test_advertisers_cannot_generate_clicks(self):
        for advertiser in (self.acme, make_advertiser("globex")):
            with self.subTest(advertiser=advertiser.username):
                self.client.force_login(advertiser)
                self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertFalse(AdClick.objects.exists())

    def test_staff_status_gives_no_bypass_for_advertisers(self):
        root = User.objects.create_superuser("root", "root@example.com", "pw-12345!")
        root.role = User.Role.ADVERTISER
        root.save()
        self.client.force_login(root)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_only_get_is_allowed(self):
        self.client.force_login(self.alice)
        for method in ("post", "head", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)
        self.assertFalse(AdClick.objects.exists())


class PortalTelemetryStatsTests(TestCase):
    def test_campaign_detail_shows_impressions_clicks_and_ctr(self):
        acme = make_advertiser("acme")
        campaign = make_campaign(acme)
        ad = make_ad_unit(campaign)
        quiet = make_ad_unit(campaign, "quiet")
        alice = make_regular("alice")
        AdImpression.objects.bulk_create([AdImpression(ad_unit=ad, user=alice) for _ in range(8)])
        AdClick.objects.create(ad_unit=ad, user=alice)
        self.client.force_login(acme)
        response = self.client.get(campaign.get_absolute_url())
        stats = {a.pk: (a.impression_count, a.click_count, a.ctr) for a in response.context["ad_units"]}
        self.assertEqual(stats[ad.pk], (8, 1, 12.5))
        self.assertEqual(stats[quiet.pk], (0, 0, None))
        self.assertContains(response, 'data-testid="ctr">12.5%<')
        self.assertContains(response, 'data-testid="ctr">—<')
