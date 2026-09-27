"""N+1 guards for the advertiser portal (see posts/tests/test_queries.py for the idea)."""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.tests.helpers import make_advertiser
from posts.tests.utils import TempMediaMixin, make_image

from .utils import make_ad_unit, make_campaign

# session + user + advertiser profile + campaigns (with ad counts)
DASHBOARD_QUERIES = 4
# session + user + campaign + ad units + advertiser profile (sponsor name)
CAMPAIGN_DETAIL_QUERIES = 5


class PortalQueryCountTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")
        self.client.force_login(self.acme)

    def count(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(ctx.captured_queries)

    def test_dashboard(self):
        url = reverse("ads:dashboard")
        make_ad_unit(make_campaign(self.acme, "first"))
        small = self.count(url)
        for i in range(8):
            campaign = make_campaign(self.acme, f"c{i}")
            for _ in range(3):
                make_ad_unit(campaign)
        large = self.count(url)
        self.assertEqual(small, large)
        self.assertEqual(large, DASHBOARD_QUERIES)

    def test_campaign_detail(self):
        campaign = make_campaign(self.acme)
        url = campaign.get_absolute_url()
        make_ad_unit(campaign)
        small = self.count(url)
        for _ in range(10):
            make_ad_unit(campaign, image=make_image())
        large = self.count(url)
        self.assertEqual(small, large)
        self.assertEqual(large, CAMPAIGN_DETAIL_QUERIES)
