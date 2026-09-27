import os
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.tests.helpers import make_advertiser, make_regular
from ads.models import AD_BODY_MAX_LENGTH, AdUnit, Campaign
from posts.tests.utils import TempMediaMixin, make_image

from .utils import make_ad_unit, make_campaign, today


class CampaignModelTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")

    def test_defaults_to_inactive(self):
        campaign = Campaign.objects.create(
            advertiser=self.acme, name="C", budget=Decimal("10"), start_date=today(), end_date=today()
        )
        self.assertEqual(campaign.status, Campaign.Status.INACTIVE)

    def test_belongs_to_advertiser(self):
        campaign = make_campaign(self.acme)
        self.assertEqual(list(self.acme.campaigns.all()), [campaign])

    def test_database_rejects_zero_budget(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_campaign(self.acme, budget=Decimal("0"))

    def test_database_rejects_negative_budget(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_campaign(self.acme, budget=Decimal("-5"))

    def test_database_rejects_end_before_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_campaign(self.acme, start_date=today(), end_date=today() - timedelta(days=1))

    def test_single_day_campaign_allowed(self):
        make_campaign(self.acme, start_date=today(), end_date=today())

    def test_database_rejects_unknown_status(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_campaign(self.acme, status="PAUSED")

    def test_name_unique_per_advertiser(self):
        make_campaign(self.acme, name="Launch")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_campaign(self.acme, name="Launch")

    def test_same_name_allowed_for_different_advertisers(self):
        make_campaign(self.acme, name="Launch")
        make_campaign(make_advertiser("globex"), name="Launch")
        self.assertEqual(Campaign.objects.filter(name="Launch").count(), 2)

    def test_full_clean_rejects_regular_user_owner(self):
        campaign = Campaign(
            advertiser=make_regular("alice"), name="X", budget=Decimal("1"),
            start_date=today(), end_date=today(),
        )
        with self.assertRaises(ValidationError) as ctx:
            campaign.full_clean()
        self.assertIn("advertiser", ctx.exception.message_dict)

    def test_full_clean_reports_constraint_messages(self):
        campaign = Campaign(
            advertiser=self.acme, name="X", budget=Decimal("0"),
            start_date=today(), end_date=today() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            campaign.full_clean()
        text = str(ctx.exception)
        self.assertIn("End date can", text)
        self.assertIn("budget", ctx.exception.message_dict)

    def test_campaigns_deleted_with_advertiser(self):
        make_campaign(self.acme)
        self.acme.delete()
        self.assertFalse(Campaign.objects.exists())


class CampaignStateTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")

    def state_of(self, **fields):
        return make_campaign(self.acme, name=str(fields), **fields).state

    def test_live(self):
        campaign = make_campaign(self.acme)
        self.assertEqual(campaign.state, Campaign.State.LIVE)
        self.assertTrue(campaign.is_live)

    def test_inactive_wins_even_within_dates(self):
        self.assertEqual(self.state_of(status=Campaign.Status.INACTIVE), Campaign.State.INACTIVE)

    def test_scheduled(self):
        start = today() + timedelta(days=3)
        self.assertEqual(
            self.state_of(start_date=start, end_date=start + timedelta(days=3)),
            Campaign.State.SCHEDULED,
        )

    def test_ended(self):
        end = today() - timedelta(days=1)
        self.assertEqual(
            self.state_of(start_date=end - timedelta(days=5), end_date=end), Campaign.State.ENDED
        )

    def test_live_on_last_day(self):
        self.assertEqual(
            self.state_of(start_date=today() - timedelta(days=5), end_date=today()),
            Campaign.State.LIVE,
        )


class AdUnitModelTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")
        self.campaign = make_campaign(self.acme)

    def test_ad_unit_belongs_to_campaign_and_derives_owner(self):
        unit = make_ad_unit(self.campaign)
        self.assertEqual(list(self.campaign.ad_units.all()), [unit])
        self.assertEqual(unit.advertiser, self.acme)

    def test_image_is_optional_and_stored_under_ads(self):
        self.assertFalse(make_ad_unit(self.campaign).image)
        unit = make_ad_unit(self.campaign, image=make_image())
        self.assertTrue(unit.image.name.startswith("ads/"))
        self.assertTrue(os.path.exists(unit.image.path))

    def test_database_rejects_empty_headline(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_ad_unit(self.campaign, headline="")

    def test_database_rejects_empty_body(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_ad_unit(self.campaign, body="")

    def test_full_clean_rejects_long_body(self):
        unit = AdUnit(
            campaign=self.campaign, headline="H", body="x" * (AD_BODY_MAX_LENGTH + 1),
            target_url="https://a.example",
        )
        with self.assertRaises(ValidationError) as ctx:
            unit.full_clean()
        self.assertIn("body", ctx.exception.message_dict)

    def test_full_clean_rejects_non_http_target_urls(self):
        for url in ("ftp://files.example/x", "javascript:alert(1)", "not a url"):
            with self.subTest(url=url):
                unit = AdUnit(campaign=self.campaign, headline="H", body="B", target_url=url)
                with self.assertRaises(ValidationError) as ctx:
                    unit.full_clean()
                self.assertIn("target_url", ctx.exception.message_dict)

    def test_full_clean_accepts_http_and_https(self):
        for url in ("http://a.example/", "https://a.example/path?q=1"):
            with self.subTest(url=url):
                AdUnit(campaign=self.campaign, headline="H", body="B", target_url=url).full_clean()

    def test_ad_units_deleted_with_campaign(self):
        make_ad_unit(self.campaign)
        self.campaign.delete()
        self.assertFalse(AdUnit.objects.exists())
