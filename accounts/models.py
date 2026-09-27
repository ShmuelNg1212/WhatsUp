from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
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
    following = models.ManyToManyField(
        "self",
        through="Follow",
        through_fields=("follower", "following"),
        symmetrical=False,
        related_name="followers",
        blank=True,
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


class Follow(models.Model):
    """
    An asymmetric edge in the social graph: `follower` sees `following`'s posts.

    No approval and no reciprocity. Only regular users take part; advertisers
    are outside the social graph (enforced by `clean()` and the social views).
    """

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_edges"
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_edges"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="accounts_follow_unique_pair",
                violation_error_message="You already follow this user.",
            ),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="accounts_follow_no_self_follow",
                violation_error_message="You can't follow yourself.",
            ),
        ]
        indexes = [
            models.Index(fields=["following", "follower"], name="accounts_follow_reverse_idx"),
        ]

    def __str__(self):
        return f"{self.follower} → {self.following}"

    def clean(self):
        super().clean()
        for field in ("follower", "following"):
            if getattr(self, f"{field}_id") and not getattr(self, field).is_regular_user:
                raise ValidationError({field: "Only regular users can follow or be followed."})
