"""
Security matrix for the advertiser portal.

Actors:  anonymous, regular user, superuser (regular role), another advertiser, the owner
Routes:  every portal URL, both GET and POST
Rule:    after every refused request, the database is unchanged.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.tests.helpers import make_advertiser, make_regular
from ads.models import AdUnit, Campaign

from .utils import make_ad_unit, make_campaign, today

User = get_user_model()


def snapshot():
    return (
        list(Campaign.objects.order_by("pk").values()),
        list(AdUnit.objects.order_by("pk").values()),
    )


def hostile_campaign_payload():
    return {
        "name": "Hijacked",
        "budget": "1.00",
        "start_date": today().isoformat(),
        "end_date": (today() + timedelta(days=1)).isoformat(),
        "status": "ACTIVE",
    }


HOSTILE_AD_PAYLOAD = {"headline": "Hijacked", "body": "Hijacked", "target_url": "https://evil.example"}


class PortalPermissionMatrixTests(TestCase):
    def setUp(self):
        self.owner = make_advertiser("acme")
        self.campaign = make_campaign(self.owner, "Acme Launch")
        self.unit = make_ad_unit(self.campaign, "Acme ad")
        c, u = self.campaign.pk, self.unit.pk

        # (url, POST payload or None when the route has no POST)
        self.global_routes = [
            (reverse("ads:dashboard"), None),
            (reverse("ads:campaign_create"), hostile_campaign_payload()),
        ]
        self.object_routes = [
            (reverse("ads:campaign_detail", args=[c]), None),
            (reverse("ads:campaign_update", args=[c]), hostile_campaign_payload()),
            (reverse("ads:campaign_delete", args=[c]), {}),
            (reverse("ads:adunit_create", args=[c]), HOSTILE_AD_PAYLOAD),
            (reverse("ads:adunit_update", args=[c, u]), HOSTILE_AD_PAYLOAD),
            (reverse("ads:adunit_delete", args=[c, u]), {}),
        ]
        self.all_routes = self.global_routes + self.object_routes

    def assert_every_request(self, routes, expected_status, check_location=None):
        before = snapshot()
        for url, payload in routes:
            with self.subTest(url=url, method="GET"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, expected_status)
                if check_location:
                    self.assertEqual(response["Location"], check_location(url))
            if payload is not None:
                with self.subTest(url=url, method="POST"):
                    response = self.client.post(url, payload)
                    self.assertEqual(response.status_code, expected_status)
        self.assertEqual(snapshot(), before, "a refused request changed the database")

    def test_anonymous_is_redirected_to_login(self):
        self.assert_every_request(
            self.all_routes, 302, check_location=lambda url: f"{reverse('login')}?next={url}"
        )

    def test_regular_user_is_forbidden(self):
        self.client.force_login(make_regular("alice"))
        self.assert_every_request(self.all_routes, 403)

    def test_regular_user_sees_403_page(self):
        self.client.force_login(make_regular("alice"))
        response = self.client.get(reverse("ads:dashboard"))
        self.assertTemplateUsed(response, "403.html")

    def test_superuser_without_advertiser_role_is_forbidden(self):
        self.client.force_login(User.objects.create_superuser("root", "root@example.com", "pw-12345!"))
        self.assert_every_request(self.all_routes, 403)

    def test_other_advertiser_gets_404_on_every_owned_object(self):
        self.client.force_login(make_advertiser("globex"))
        self.assert_every_request(self.object_routes, 404)

    def test_other_advertiser_dashboard_hides_foreign_campaigns(self):
        self.client.force_login(make_advertiser("globex"))
        response = self.client.get(reverse("ads:dashboard"))
        self.assertEqual(response.context["campaigns"], [])
        self.assertNotContains(response, "Acme Launch")

    def test_owner_can_reach_every_route(self):
        self.client.force_login(self.owner)
        for url, _ in self.all_routes:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class NestedOwnershipTests(TestCase):
    """The unit must belong to the campaign in the URL, and the campaign to the requester."""

    def setUp(self):
        self.acme = make_advertiser("acme")
        self.acme_a = make_campaign(self.acme, "A")
        self.acme_b = make_campaign(self.acme, "B")
        self.unit_in_b = make_ad_unit(self.acme_b, "in B")

        self.globex = make_advertiser("globex")
        self.globex_campaign = make_campaign(self.globex, "G")
        self.globex_unit = make_ad_unit(self.globex_campaign, "globex ad")
        self.client.force_login(self.acme)

    def assert_404_and_unchanged(self, url, payload):
        before = snapshot()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, payload).status_code, 404)
        self.assertEqual(snapshot(), before)

    def test_own_unit_under_own_but_wrong_campaign(self):
        for name in ("adunit_update", "adunit_delete"):
            with self.subTest(view=name):
                url = reverse(f"ads:{name}", args=[self.acme_a.pk, self.unit_in_b.pk])
                self.assert_404_and_unchanged(url, HOSTILE_AD_PAYLOAD)

    def test_foreign_unit_under_own_campaign(self):
        for name in ("adunit_update", "adunit_delete"):
            with self.subTest(view=name):
                url = reverse(f"ads:{name}", args=[self.acme_a.pk, self.globex_unit.pk])
                self.assert_404_and_unchanged(url, HOSTILE_AD_PAYLOAD)

    def test_creating_ad_in_foreign_campaign(self):
        url = reverse("ads:adunit_create", args=[self.globex_campaign.pk])
        self.assert_404_and_unchanged(url, HOSTILE_AD_PAYLOAD)

    def test_nonexistent_ids(self):
        for url in (
            reverse("ads:campaign_detail", args=[9999]),
            reverse("ads:adunit_update", args=[self.acme_a.pk, 9999]),
            reverse("ads:adunit_create", args=[9999]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class AdvertiserStillExcludedFromSocialTests(TestCase):
    def test_advertiser_cannot_post_to_feed(self):
        self.client.force_login(make_advertiser("acme"))
        self.assertEqual(self.client.post(reverse("posts:feed"), {"body": "ad spam"}).status_code, 403)
