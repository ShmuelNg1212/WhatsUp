"""Unit tests for the gating helpers, independent of any real app view."""

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from accounts.models import User
from accounts.permissions import RoleRequiredMixin, role_required

from .helpers import make_advertiser, make_regular


class AdvertiserOnlyView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.ADVERTISER,)

    def get(self, request):
        return HttpResponse("ok")


class EitherRoleView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.ADVERTISER, User.Role.REGULAR_USER)

    def get(self, request):
        return HttpResponse("ok")


class MisconfiguredView(RoleRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


@role_required(User.Role.ADVERTISER)
def advertiser_only(request):
    return HttpResponse("ok")


class PermissionHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request_as(self, user):
        request = self.factory.get("/protected/")
        request.user = user
        return request

    # Mixin
    def test_mixin_allows_matching_role(self):
        response = AdvertiserOnlyView.as_view()(self.request_as(make_advertiser()))
        self.assertEqual(response.status_code, 200)

    def test_mixin_denies_other_role(self):
        with self.assertRaises(PermissionDenied):
            AdvertiserOnlyView.as_view()(self.request_as(make_regular()))

    def test_mixin_redirects_anonymous(self):
        response = AdvertiserOnlyView.as_view()(self.request_as(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/?next=/protected/", response.url)

    def test_mixin_supports_multiple_roles(self):
        view = EitherRoleView.as_view()
        self.assertEqual(view(self.request_as(make_regular())).status_code, 200)
        self.assertEqual(view(self.request_as(make_advertiser())).status_code, 200)

    def test_mixin_without_roles_is_misconfigured(self):
        with self.assertRaises(ImproperlyConfigured):
            MisconfiguredView.as_view()(self.request_as(make_regular()))

    # Decorator
    def test_decorator_allows_matching_role(self):
        self.assertEqual(advertiser_only(self.request_as(make_advertiser())).status_code, 200)

    def test_decorator_denies_other_role(self):
        with self.assertRaises(PermissionDenied):
            advertiser_only(self.request_as(make_regular()))

    def test_decorator_redirects_anonymous(self):
        response = advertiser_only(self.request_as(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/?next=/protected/", response.url)

    def test_decorator_without_roles_is_misconfigured(self):
        with self.assertRaises(ImproperlyConfigured):
            role_required()

    def test_decorator_preserves_view_name(self):
        self.assertEqual(advertiser_only.__name__, "advertiser_only")
