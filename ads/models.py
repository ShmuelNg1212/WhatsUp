from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator, URLValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class AdvertiserProfile(models.Model):
    """
    Business details for an advertiser account.

    Invariant: only users with role ADVERTISER have a profile. The database
    cannot enforce a rule across two tables, so `clean()` enforces it for
    forms and the admin, and advertiser signup creates the user and profile
    in one transaction.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advertiser_profile",
    )
    company_name = models.CharField(max_length=200)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name

    def clean(self):
        super().clean()
        if self.user_id is not None and not self.user.is_advertiser:
            raise ValidationError(
                {"user": "Only advertiser accounts can have an advertiser profile."}
            )


class Campaign(models.Model):
    """
    A budgeted advertising campaign owned by exactly one advertiser.

    Ownership is `advertiser`, set from request.user by the portal and never
    exposed as a form field. See ads/mixins.py for how views enforce it.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class State(models.TextChoices):
        """Derived display state; not stored."""

        LIVE = "live", "Live"
        SCHEDULED = "scheduled", "Scheduled"
        ENDED = "ended", "Ended"
        INACTIVE = "inactive", "Inactive"

    advertiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaigns",
        limit_choices_to={"role": "ADVERTISER"},
    )
    name = models.CharField(max_length=120)
    budget = models.DecimalField(
        "total budget (USD)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status, default=Status.INACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["advertiser", "name"],
                name="ads_campaign_unique_name_per_advertiser",
                violation_error_message="You already have a campaign with this name.",
            ),
            models.CheckConstraint(
                condition=models.Q(budget__gt=0),
                name="ads_campaign_budget_positive",
                violation_error_message="Budget must be greater than zero.",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ads_campaign_end_after_start",
                violation_error_message="End date can't be before the start date.",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "INACTIVE"]),
                name="ads_campaign_status_valid",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("ads:campaign_detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.advertiser_id is not None and not self.advertiser.is_advertiser:
            raise ValidationError({"advertiser": "Only advertiser accounts can own campaigns."})

    @property
    def state(self):
        if self.status != self.Status.ACTIVE:
            return self.State.INACTIVE
        today = timezone.localdate()
        if today < self.start_date:
            return self.State.SCHEDULED
        if today > self.end_date:
            return self.State.ENDED
        return self.State.LIVE

    @property
    def is_live(self):
        return self.state == self.State.LIVE


AD_HEADLINE_MAX_LENGTH = 90
AD_BODY_MAX_LENGTH = 300


class AdUnit(models.Model):
    """
    One advertisement inside a campaign. Its owner is always derived from
    `campaign.advertiser` and never stored separately.
    """

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="ad_units")
    headline = models.CharField(max_length=AD_HEADLINE_MAX_LENGTH)
    body = models.TextField(
        "body text",
        max_length=AD_BODY_MAX_LENGTH,
        validators=[MaxLengthValidator(AD_BODY_MAX_LENGTH)],
    )
    image = models.ImageField(upload_to="ads/%Y/%m/", blank=True)
    target_url = models.URLField(
        "target URL",
        max_length=500,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Where people go when they click the ad (http or https).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(headline=""),
                name="ads_adunit_headline_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(body=""),
                name="ads_adunit_body_not_empty",
            ),
        ]
        indexes = [
            models.Index(fields=["campaign", "created_at"], name="ads_adunit_campaign_time_idx"),
        ]

    def __str__(self):
        return self.headline

    @property
    def advertiser(self):
        return self.campaign.advertiser
