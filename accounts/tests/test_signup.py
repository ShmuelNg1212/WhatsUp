from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from ads.models import AdvertiserProfile

from .helpers import PASSWORD, make_regular


def regular_payload(**overrides):
    data = {
        "username": "alice",
        "email": "alice@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


def advertiser_payload(**overrides):
    data = regular_payload(
        username="acme",
        email="ads@acme.com",
        company_name="Acme Inc.",
        website="https://acme.com",
    )
    data.update(overrides)
    return data


class RegularSignupTests(TestCase):
    url = reverse("signup")

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your account")

    def test_creates_regular_user_and_logs_in(self):
        response = self.client.post(self.url, regular_payload())
        self.assertRedirects(response, reverse("home"), target_status_code=302)
        user = User.objects.get(username="alice")
        self.assertEqual(user.role, User.Role.REGULAR_USER)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertFalse(AdvertiserProfile.objects.exists())

    def test_role_cannot_be_escalated_via_post_data(self):
        self.client.post(self.url, regular_payload(role="ADVERTISER"))
        self.assertEqual(User.objects.get().role, User.Role.REGULAR_USER)

    def test_email_is_required(self):
        response = self.client.post(self.url, regular_payload(email=""))
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_duplicate_email_rejected_case_insensitively(self):
        make_regular("existing")
        response = self.client.post(self.url, regular_payload(email="EXISTING@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_rejected(self):
        make_regular("alice")
        response = self.client.post(self.url, regular_payload(email="other@example.com"))
        self.assertIn("username", response.context["form"].errors)

    def test_password_mismatch_rejected(self):
        response = self.client.post(self.url, regular_payload(password2="different-99"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, regular_payload(password1="123", password2="123"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_logged_in_user_is_redirected_away(self):
        self.client.force_login(make_regular())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home"), target_status_code=302)


class AdvertiserSignupTests(TestCase):
    url = reverse("signup_advertiser")

    def test_page_renders_with_company_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create an advertiser account")
        self.assertContains(response, 'name="company_name"')

    def test_creates_advertiser_with_profile_and_logs_in(self):
        response = self.client.post(self.url, advertiser_payload())
        self.assertRedirects(response, reverse("home"), target_status_code=302)
        user = User.objects.get(username="acme")
        self.assertEqual(user.role, User.Role.ADVERTISER)
        self.assertEqual(user.advertiser_profile.company_name, "Acme Inc.")
        self.assertEqual(user.advertiser_profile.website, "https://acme.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_website_is_optional(self):
        self.client.post(self.url, advertiser_payload(website=""))
        self.assertEqual(User.objects.get().advertiser_profile.website, "")

    def test_company_name_is_required(self):
        response = self.client.post(self.url, advertiser_payload(company_name=""))
        self.assertIn("company_name", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_invalid_website_rejected(self):
        response = self.client.post(self.url, advertiser_payload(website="not a url"))
        self.assertIn("website", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_user_and_profile_are_created_atomically(self):
        with mock.patch.object(AdvertiserProfile, "save", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, advertiser_payload())
        self.assertFalse(User.objects.exists())
        self.assertFalse(AdvertiserProfile.objects.exists())
