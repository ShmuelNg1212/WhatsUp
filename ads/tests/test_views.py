from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.helpers import make_advertiser
from ads.models import AdUnit, Campaign
from posts.tests.utils import TempMediaMixin, make_image

from .utils import make_ad_unit, make_campaign, today

DASHBOARD = reverse("ads:dashboard")
CAMPAIGN_CREATE = reverse("ads:campaign_create")


def campaign_payload(**overrides):
    data = {
        "name": "Launch",
        "budget": "1500.00",
        "start_date": today().isoformat(),
        "end_date": (today() + timedelta(days=14)).isoformat(),
        "status": "ACTIVE",
    }
    data.update(overrides)
    return data


def ad_payload(**overrides):
    data = {"headline": "Try Acme", "body": "The best anvils.", "target_url": "https://acme.example"}
    data.update(overrides)
    return data


class DashboardTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme", company_name="Acme Inc.")
        self.client.force_login(self.acme)

    def test_empty_state(self):
        response = self.client.get(DASHBOARD)
        self.assertContains(response, "No campaigns yet.")
        self.assertContains(response, "Acme Inc.")
        self.assertContains(response, f'href="{CAMPAIGN_CREATE}"')

    def test_lists_only_my_campaigns_with_stats(self):
        live = make_campaign(self.acme, "Live one", budget=Decimal("100"))
        make_ad_unit(live)
        make_ad_unit(live)
        make_campaign(self.acme, "Paused", budget=Decimal("50.50"), status=Campaign.Status.INACTIVE)
        make_campaign(make_advertiser("globex"), "Not mine")
        response = self.client.get(DASHBOARD)
        names = [c.name for c in response.context["campaigns"]]
        self.assertCountEqual(names, ["Live one", "Paused"])
        self.assertNotContains(response, "Not mine")
        self.assertContains(response, 'data-testid="campaign-count">2<')
        self.assertContains(response, 'data-testid="live-count">1<')
        self.assertContains(response, 'data-testid="total-budget">$150.50<')
        ad_counts = {c.name: c.ad_count for c in response.context["campaigns"]}
        self.assertEqual(ad_counts, {"Live one": 2, "Paused": 0})

    def test_state_badges(self):
        make_campaign(self.acme, "Soon", start_date=today() + timedelta(days=2), end_date=today() + timedelta(days=9))
        response = self.client.get(DASHBOARD)
        self.assertContains(response, 'data-state="scheduled"')

    def test_advertiser_nav_links(self):
        response = self.client.get(DASHBOARD)
        self.assertContains(response, f'href="{DASHBOARD}"')
        self.assertContains(response, f'href="{CAMPAIGN_CREATE}"')


class CampaignCreateTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")
        self.client.force_login(self.acme)

    def test_form_renders_with_date_inputs(self):
        response = self.client.get(CAMPAIGN_CREATE)
        self.assertContains(response, 'type="date"', count=2)
        self.assertNotContains(response, 'name="advertiser"')

    def test_create_campaign(self):
        response = self.client.post(CAMPAIGN_CREATE, campaign_payload())
        campaign = Campaign.objects.get()
        self.assertRedirects(response, campaign.get_absolute_url())
        self.assertEqual(campaign.advertiser, self.acme)
        self.assertEqual(campaign.budget, Decimal("1500.00"))
        self.assertEqual(campaign.status, Campaign.Status.ACTIVE)
        self.assertEqual(campaign.get_absolute_url(), f"/ads/campaigns/{campaign.pk}/")

    def test_owner_cannot_be_injected(self):
        globex = make_advertiser("globex")
        self.client.post(CAMPAIGN_CREATE, campaign_payload(advertiser=globex.pk))
        self.assertEqual(Campaign.objects.get().advertiser, self.acme)

    def test_status_is_required_and_preselected_inactive(self):
        data = campaign_payload()
        data.pop("status")
        response = self.client.post(CAMPAIGN_CREATE, data)
        self.assertIn("status", response.context["form"].errors)
        self.assertEqual(
            self.client.get(CAMPAIGN_CREATE).context["form"]["status"].value(), Campaign.Status.INACTIVE
        )

    def assert_rejected(self, field, **overrides):
        response = self.client.post(CAMPAIGN_CREATE, campaign_payload(**overrides))
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors)
        self.assertFalse(Campaign.objects.exists())
        return response

    def test_rejects_zero_budget(self):
        self.assert_rejected("budget", budget="0")

    def test_rejects_negative_budget(self):
        self.assert_rejected("budget", budget="-10")

    def test_rejects_end_before_start(self):
        response = self.assert_rejected(
            "end_date", end_date=(today() - timedelta(days=1)).isoformat()
        )
        self.assertContains(response, "End date can&#x27;t be before the start date.")

    def test_rejects_past_start_on_create(self):
        response = self.assert_rejected(
            "start_date", start_date=(today() - timedelta(days=1)).isoformat()
        )
        self.assertContains(response, "can&#x27;t start in the past")

    def test_rejects_duplicate_name_case_insensitively(self):
        make_campaign(self.acme, "Launch")
        self.client.post(CAMPAIGN_CREATE, campaign_payload(name="LAUNCH"))
        self.assertEqual(Campaign.objects.count(), 1)

    def test_other_advertisers_can_reuse_a_name(self):
        make_campaign(make_advertiser("globex"), "Launch")
        self.client.post(CAMPAIGN_CREATE, campaign_payload(name="Launch"))
        self.assertEqual(Campaign.objects.filter(advertiser=self.acme).count(), 1)

    def test_rejects_missing_fields(self):
        response = self.client.post(CAMPAIGN_CREATE, {})
        self.assertEqual(
            set(response.context["form"].errors),
            {"name", "budget", "start_date", "end_date", "status"},
        )


class CampaignDetailUpdateDeleteTests(TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme", company_name="Acme Inc.")
        self.campaign = make_campaign(self.acme, "Launch")
        self.client.force_login(self.acme)

    def test_detail_shows_parameters_and_ad_previews(self):
        make_ad_unit(self.campaign, "Anvils on sale")
        response = self.client.get(self.campaign.get_absolute_url())
        self.assertContains(response, "Launch")
        self.assertContains(response, "$500.00")
        self.assertContains(response, "Anvils on sale")
        self.assertContains(response, "Sponsored")
        self.assertContains(response, "Acme Inc.")
        self.assertContains(response, 'rel="sponsored noopener noreferrer"')

    def test_detail_empty_ad_state(self):
        response = self.client.get(self.campaign.get_absolute_url())
        self.assertContains(response, "No ad units yet.")

    def test_update(self):
        url = reverse("ads:campaign_update", args=[self.campaign.pk])
        response = self.client.post(url, campaign_payload(name="Launch v2", status="INACTIVE", budget="99.99"))
        self.assertRedirects(response, self.campaign.get_absolute_url())
        self.campaign.refresh_from_db()
        self.assertEqual((self.campaign.name, self.campaign.status), ("Launch v2", "INACTIVE"))
        self.assertEqual(self.campaign.budget, Decimal("99.99"))

    def test_update_allows_keeping_a_past_start_date(self):
        started = make_campaign(
            self.acme, "Running", start_date=today() - timedelta(days=10)
        )
        url = reverse("ads:campaign_update", args=[started.pk])
        response = self.client.post(
            url,
            campaign_payload(name="Running", start_date=started.start_date.isoformat()),
        )
        self.assertRedirects(response, started.get_absolute_url())

    def test_update_can_keep_own_name(self):
        url = reverse("ads:campaign_update", args=[self.campaign.pk])
        response = self.client.post(url, campaign_payload(name="Launch"))
        self.assertEqual(response.status_code, 302)

    def test_update_rejects_name_of_another_own_campaign(self):
        make_campaign(self.acme, "Other")
        url = reverse("ads:campaign_update", args=[self.campaign.pk])
        response = self.client.post(url, campaign_payload(name="other"))
        self.assertIn("name", response.context["form"].errors)

    def test_update_cannot_change_owner(self):
        globex = make_advertiser("globex")
        url = reverse("ads:campaign_update", args=[self.campaign.pk])
        self.client.post(url, campaign_payload(name="Launch", advertiser=globex.pk))
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.advertiser, self.acme)

    def test_delete_confirmation_warns_about_ad_units(self):
        make_ad_unit(self.campaign)
        make_ad_unit(self.campaign)
        response = self.client.get(reverse("ads:campaign_delete", args=[self.campaign.pk]))
        self.assertContains(response, 'data-testid="ad-count">2<')
        self.assertTrue(Campaign.objects.exists())

    def test_delete_removes_campaign_and_ad_units(self):
        make_ad_unit(self.campaign)
        response = self.client.post(reverse("ads:campaign_delete", args=[self.campaign.pk]), follow=True)
        self.assertRedirects(response, DASHBOARD)
        self.assertContains(response, "Campaign “Launch” deleted.")
        self.assertFalse(Campaign.objects.exists())
        self.assertFalse(AdUnit.objects.exists())


class AdUnitCrudTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.acme = make_advertiser("acme")
        self.campaign = make_campaign(self.acme)
        self.create_url = reverse("ads:adunit_create", args=[self.campaign.pk])
        self.client.force_login(self.acme)

    def test_form_renders_without_campaign_field(self):
        response = self.client.get(self.create_url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, 'name="campaign"')
        self.assertEqual(response.context["campaign"], self.campaign)

    def test_create_text_ad(self):
        response = self.client.post(self.create_url, ad_payload())
        self.assertRedirects(response, self.campaign.get_absolute_url())
        unit = AdUnit.objects.get()
        self.assertEqual((unit.campaign, unit.headline), (self.campaign, "Try Acme"))
        self.assertFalse(unit.image)

    def test_create_ad_with_image(self):
        self.client.post(self.create_url, ad_payload(image=make_image("banner.png")))
        unit = AdUnit.objects.get()
        self.assertTrue(unit.image.name.startswith("ads/"))
        self.assertContains(self.client.get(self.campaign.get_absolute_url()), unit.image.url)

    def test_bare_domain_gets_https(self):
        self.client.post(self.create_url, ad_payload(target_url="acme.example/deals"))
        self.assertEqual(AdUnit.objects.get().target_url, "https://acme.example/deals")

    def test_campaign_cannot_be_injected(self):
        other = make_campaign(make_advertiser("globex"), "Theirs")
        self.client.post(self.create_url, ad_payload(campaign=other.pk))
        self.assertEqual(AdUnit.objects.get().campaign, self.campaign)

    def assert_rejected(self, field, **overrides):
        response = self.client.post(self.create_url, ad_payload(**overrides))
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors)
        self.assertFalse(AdUnit.objects.exists())

    def test_rejects_non_http_urls(self):
        for url in ("ftp://acme.example/", "javascript:alert(1)"):
            with self.subTest(url=url):
                self.assert_rejected("target_url", target_url=url)

    def test_rejects_long_headline(self):
        self.assert_rejected("headline", headline="x" * 91)

    def test_rejects_long_body(self):
        self.assert_rejected("body", body="x" * 301)

    def test_rejects_empty_body(self):
        self.assert_rejected("body", body="")

    def test_rejects_non_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        self.assert_rejected("image", image=fake)

    def test_rejects_oversized_image(self):
        from unittest import mock

        with mock.patch("core.validators.MAX_IMAGE_BYTES", 10):
            self.assert_rejected("image", image=make_image())

    def test_update(self):
        unit = make_ad_unit(self.campaign)
        url = reverse("ads:adunit_update", args=[self.campaign.pk, unit.pk])
        response = self.client.post(url, ad_payload(headline="New headline"))
        self.assertRedirects(response, self.campaign.get_absolute_url())
        unit.refresh_from_db()
        self.assertEqual(unit.headline, "New headline")

    def test_update_cannot_move_ad_to_another_campaign(self):
        unit = make_ad_unit(self.campaign)
        mine_too = make_campaign(self.acme, "Second")
        url = reverse("ads:adunit_update", args=[self.campaign.pk, unit.pk])
        self.client.post(url, ad_payload(campaign=mine_too.pk))
        unit.refresh_from_db()
        self.assertEqual(unit.campaign, self.campaign)

    def test_delete_with_confirmation(self):
        unit = make_ad_unit(self.campaign, "Doomed")
        url = reverse("ads:adunit_delete", args=[self.campaign.pk, unit.pk])
        self.assertContains(self.client.get(url), "Delete the ad “Doomed”?")
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, self.campaign.get_absolute_url())
        self.assertContains(response, "Ad “Doomed” deleted.")
        self.assertFalse(AdUnit.objects.exists())
        self.assertTrue(Campaign.objects.exists())
