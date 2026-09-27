from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


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
