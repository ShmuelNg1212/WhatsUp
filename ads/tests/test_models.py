from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from ads.models import AdvertiserProfile


def make_advertiser(username="acme"):
    return User.objects.create_user(
        username, f"{username}@example.com", "pw-12345!", role=User.Role.ADVERTISER
    )


class AdvertiserProfileTests(TestCase):
    def test_profile_is_reachable_from_user(self):
        user = make_advertiser()
        profile = AdvertiserProfile.objects.create(user=user, company_name="Acme")
        self.assertEqual(user.advertiser_profile, profile)
        self.assertEqual(str(profile), "Acme")

    def test_valid_profile_passes_full_clean(self):
        profile = AdvertiserProfile(
            user=make_advertiser(), company_name="Acme", website="https://acme.com"
        )
        profile.full_clean()

    def test_regular_user_cannot_have_profile(self):
        regular = User.objects.create_user("bob", "bob@example.com", "pw-12345!")
        profile = AdvertiserProfile(user=regular, company_name="Nope")
        with self.assertRaises(ValidationError) as ctx:
            profile.full_clean()
        self.assertIn("user", ctx.exception.message_dict)

    def test_one_profile_per_user(self):
        user = make_advertiser()
        AdvertiserProfile.objects.create(user=user, company_name="Acme")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdvertiserProfile.objects.create(user=user, company_name="Acme 2")

    def test_company_name_is_required(self):
        profile = AdvertiserProfile(user=make_advertiser(), company_name="")
        with self.assertRaises(ValidationError) as ctx:
            profile.full_clean()
        self.assertIn("company_name", ctx.exception.message_dict)

    def test_website_is_optional_but_validated(self):
        profile = AdvertiserProfile(
            user=make_advertiser(), company_name="Acme", website="not a url"
        )
        with self.assertRaises(ValidationError) as ctx:
            profile.full_clean()
        self.assertIn("website", ctx.exception.message_dict)

    def test_profile_deleted_with_user(self):
        user = make_advertiser()
        AdvertiserProfile.objects.create(user=user, company_name="Acme")
        user.delete()
        self.assertFalse(AdvertiserProfile.objects.exists())
