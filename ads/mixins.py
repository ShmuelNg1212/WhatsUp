"""
Access control for the advertiser portal. Every portal view uses one of these.

Layer 1, role: `AdvertiserRequiredMixin` runs in dispatch(), before any query.
    Anonymous visitors → login redirect. Non-advertisers → 403.

Layer 2, ownership: objects are only ever fetched through querysets already
    filtered to request.user. Another advertiser's IDs are simply not found
    (404), which also avoids revealing that they exist. Owners (`advertiser`,
    `campaign`) are set on the server, never taken from form data.
"""

from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from accounts.models import User
from accounts.permissions import RoleRequiredMixin

from .models import AdUnit, Campaign


def campaigns_owned_by(user):
    return Campaign.objects.filter(advertiser=user)


class AdvertiserRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADVERTISER,)


class OwnedCampaignMixin(AdvertiserRequiredMixin):
    """For generic views acting on one Campaign (`pk` in the URL)."""

    model = Campaign

    def get_queryset(self):
        return campaigns_owned_by(self.request.user)


class OwnedAdUnitMixin(AdvertiserRequiredMixin):
    """
    For generic views nested under /campaigns/<campaign_pk>/units/.

    The parent campaign must belong to request.user, and the unit (`pk`) must
    belong to that campaign; otherwise 404.
    """

    model = AdUnit

    @cached_property
    def campaign(self):
        return get_object_or_404(campaigns_owned_by(self.request.user), pk=self.kwargs["campaign_pk"])

    def get_queryset(self):
        return AdUnit.objects.filter(campaign=self.campaign)

    def get_context_data(self, **kwargs):
        kwargs.setdefault("campaign", self.campaign)
        return super().get_context_data(**kwargs)
