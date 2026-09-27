from datetime import timedelta

from django.contrib import admin
from django.test import RequestFactory, TestCase

from accounts.models import User
from accounts.tests.helpers import make_advertiser, make_regular
from ads.models import AdClick, AdImpression, AdUnit, Campaign

from .utils import make_ad_unit, make_campaign, today


class ServableQuerySetTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")
        d = timedelta(days=1)
        self.cases = {
            "live": make_campaign(self.acme, "live"),
            "live_last_day": make_campaign(self.acme, "last", start_date=today() - 5 * d, end_date=today()),
            "live_first_day": make_campaign(self.acme, "first", start_date=today(), end_date=today() + d),
            "inactive": make_campaign(self.acme, "inactive", status=Campaign.Status.INACTIVE),
            "scheduled": make_campaign(self.acme, "scheduled", start_date=today() + d, end_date=today() + 5 * d),
            "ended": make_campaign(self.acme, "ended", start_date=today() - 5 * d, end_date=today() - d),
        }
        self.units = {name: make_ad_unit(c, name) for name, c in self.cases.items()}

    def test_servable_matches_is_live_for_every_state(self):
        servable = set(AdUnit.objects.servable())
        for name, unit in self.units.items():
            with self.subTest(case=name):
                self.assertEqual(unit in servable, unit.campaign.is_live)

    def test_only_live_campaigns_are_servable(self):
        self.assertCountEqual(
            [u.headline for u in AdUnit.objects.servable()],
            ["live", "live_last_day", "live_first_day"],
        )

    def test_campaign_live_queryset_matches_property(self):
        live = set(Campaign.objects.live())
        for campaign in Campaign.objects.all():
            with self.subTest(campaign=campaign.name):
                self.assertEqual(campaign in live, campaign.is_live)

    def test_servable_accepts_explicit_date(self):
        tomorrow = today() + timedelta(days=1)
        self.assertIn(self.units["scheduled"], AdUnit.objects.servable(tomorrow))
        self.assertNotIn(self.units["live_last_day"], AdUnit.objects.servable(tomorrow))


class SponsorNameTests(TestCase):
    def test_company_name_when_profile_exists(self):
        unit = make_ad_unit(make_campaign(make_advertiser("acme", company_name="Acme Inc.")))
        self.assertEqual(unit.sponsor_name, "Acme Inc.")

    def test_username_when_profile_missing(self):
        bare = User.objects.create_user("bare", "b@example.com", "pw-12345!", role=User.Role.ADVERTISER)
        self.assertEqual(make_ad_unit(make_campaign(bare)).sponsor_name, "bare")

    def test_no_queries_when_select_related(self):
        make_ad_unit(make_campaign(make_advertiser("acme")))
        unit = AdUnit.objects.select_related("campaign__advertiser__advertiser_profile").get()
        with self.assertNumQueries(0):
            unit.sponsor_name


class TelemetryModelTests(TestCase):
    def setUp(self):
        self.unit = make_ad_unit(make_campaign(make_advertiser("acme")))
        self.alice = make_regular("alice")

    def test_records_ad_user_and_time(self):
        for model in (AdImpression, AdClick):
            with self.subTest(model=model.__name__):
                event = model.objects.create(ad_unit=self.unit, user=self.alice)
                self.assertEqual((event.ad_unit, event.user), (self.unit, self.alice))
                self.assertIsNotNone(event.created_at)

    def test_reverse_accessors(self):
        AdImpression.objects.create(ad_unit=self.unit, user=self.alice)
        AdClick.objects.create(ad_unit=self.unit, user=self.alice)
        self.assertEqual(self.unit.impressions.count(), 1)
        self.assertEqual(self.unit.clicks.count(), 1)
        self.assertEqual(self.alice.ad_impressions.count(), 1)
        self.assertEqual(self.alice.ad_clicks.count(), 1)

    def test_deleting_viewer_keeps_stats(self):
        AdImpression.objects.create(ad_unit=self.unit, user=self.alice)
        AdClick.objects.create(ad_unit=self.unit, user=self.alice)
        self.alice.delete()
        self.assertEqual(self.unit.impressions.get().user, None)
        self.assertEqual(self.unit.clicks.get().user, None)

    def test_deleting_ad_removes_its_telemetry(self):
        AdImpression.objects.create(ad_unit=self.unit, user=self.alice)
        AdClick.objects.create(ad_unit=self.unit, user=self.alice)
        self.unit.delete()
        self.assertFalse(AdImpression.objects.exists())
        self.assertFalse(AdClick.objects.exists())

    def test_str(self):
        event = AdClick.objects.create(ad_unit=self.unit, user=self.alice)
        self.assertIn(f"ad={self.unit.pk}", str(event))


class TelemetryAdminIsReadOnlyTests(TestCase):
    def test_no_add_change_delete(self):
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser("root", "root@example.com", "pw-12345!")
        for model in (AdImpression, AdClick):
            model_admin = admin.site._registry[model]
            with self.subTest(model=model.__name__):
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
