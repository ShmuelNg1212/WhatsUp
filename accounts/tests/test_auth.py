from django.test import TestCase
from django.urls import reverse

from .helpers import PASSWORD, make_advertiser, make_regular


class LoginTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_lands_on_feed(self):
        make_regular("alice")
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": PASSWORD}, follow=True
        )
        self.assertRedirects(response, reverse("posts:feed"))

    def test_advertiser_lands_on_dashboard(self):
        make_advertiser("acme")
        response = self.client.post(
            reverse("login"), {"username": "acme", "password": PASSWORD}, follow=True
        )
        self.assertRedirects(response, reverse("ads:dashboard"))

    def test_next_parameter_is_honoured(self):
        make_regular("alice")
        response = self.client.post(
            reverse("login") + "?next=/feed/",
            {"username": "alice", "password": PASSWORD, "next": "/feed/"},
        )
        self.assertRedirects(response, "/feed/")

    def test_wrong_password_is_rejected(self):
        make_regular("alice")
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_log_in(self):
        user = make_regular("alice")
        user.is_active = False
        user.save()
        self.client.post(reverse("login"), {"username": "alice", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)


class LogoutTests(TestCase):
    def test_logout_via_post(self):
        self.client.force_login(make_regular())
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_via_get_is_not_allowed(self):
        self.client.force_login(make_regular())
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


class HomeRoutingTests(TestCase):
    def test_anonymous_sees_landing_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")
        self.assertContains(response, reverse("signup_advertiser"))

    def test_regular_user_redirected_to_feed(self):
        self.client.force_login(make_regular())
        self.assertRedirects(self.client.get(reverse("home")), reverse("posts:feed"))

    def test_advertiser_redirected_to_dashboard(self):
        self.client.force_login(make_advertiser())
        self.assertRedirects(self.client.get(reverse("home")), reverse("ads:dashboard"))
