"""
The role-gating matrix: every protected area against every kind of visitor.

/feed/  is protected with RoleRequiredMixin (class-based view)
/ads/   is protected with @role_required     (function view)
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .helpers import make_advertiser, make_regular

FEED = reverse("posts:feed")
ADS = reverse("ads:dashboard")


class AnonymousGatingTests(TestCase):
    def test_feed_redirects_to_login(self):
        self.assertRedirects(self.client.get(FEED), f"{reverse('login')}?next={FEED}")

    def test_ads_redirects_to_login(self):
        self.assertRedirects(self.client.get(ADS), f"{reverse('login')}?next={ADS}")


class RegularUserGatingTests(TestCase):
    def setUp(self):
        self.client.force_login(make_regular())

    def test_can_access_feed(self):
        response = self.client.get(FEED)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/feed.html")

    def test_is_forbidden_from_ads(self):
        response = self.client.get(ADS)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")


class AdvertiserGatingTests(TestCase):
    def setUp(self):
        self.client.force_login(make_advertiser(company_name="Acme Inc."))

    def test_can_access_ads_dashboard(self):
        response = self.client.get(ADS)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme Inc.")

    def test_is_forbidden_from_feed(self):
        response = self.client.get(FEED)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")

    def test_dashboard_handles_missing_profile(self):
        orphan = User.objects.create_user(
            "noprofile", "np@example.com", "pw-12345!", role=User.Role.ADVERTISER
        )
        self.client.force_login(orphan)
        response = self.client.get(ADS)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no company profile")


class SuperuserGatingTests(TestCase):
    """Staff status grants no bypass: gating follows the role alone."""

    def setUp(self):
        admin = User.objects.create_superuser("root", "root@example.com", "pw-12345!")
        self.client.force_login(admin)

    def test_superuser_with_regular_role_is_forbidden_from_ads(self):
        self.assertEqual(self.client.get(ADS).status_code, 403)

    def test_superuser_can_open_admin(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
