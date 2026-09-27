from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """
    The single account model for every person on the platform.

    A user's `role` decides which area of the site they may use. Business
    data that only advertisers have lives in `ads.AdvertiserProfile`.
    """

    class Role(models.TextChoices):
        REGULAR_USER = "REGULAR_USER", "Regular user"
        ADVERTISER = "ADVERTISER", "Advertiser"

    email = models.EmailField("email address")
    role = models.CharField(
        max_length=20,
        choices=Role,
        default=Role.REGULAR_USER,
        db_index=True,
    )

    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["REGULAR_USER", "ADVERTISER"]),
                name="accounts_user_role_valid",
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message="A user with that email already exists.",
            ),
        ]

    @property
    def is_regular_user(self):
        return self.role == self.Role.REGULAR_USER

    @property
    def is_advertiser(self):
        return self.role == self.Role.ADVERTISER
