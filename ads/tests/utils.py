from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from ads.models import AdUnit, Campaign


def today():
    return timezone.localdate()


def make_campaign(advertiser, name="Summer Sale", **overrides):
    fields = {
        "budget": Decimal("500.00"),
        "start_date": today(),
        "end_date": today() + timedelta(days=30),
        "status": Campaign.Status.ACTIVE,
    }
    fields.update(overrides)
    return Campaign.objects.create(advertiser=advertiser, name=name, **fields)


def make_ad_unit(campaign, headline="Big savings", **overrides):
    fields = {"body": "Everything 50% off this week.", "target_url": "https://acme.example/sale"}
    fields.update(overrides)
    return AdUnit.objects.create(campaign=campaign, headline=headline, **fields)
