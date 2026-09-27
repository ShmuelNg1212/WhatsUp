"""
Role-based access control for views.

Both helpers follow the same rules:
- Anonymous visitors are redirected to the login page (with ?next=).
- Logged-in users whose role is not allowed get 403 Forbidden.

Usage:
    class FeedView(RoleRequiredMixin, TemplateView):
        allowed_roles = (User.Role.REGULAR_USER,)

    @role_required(User.Role.ADVERTISER)
    def dashboard(request): ...
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied


def _check_role(user, allowed_roles):
    if user.role not in allowed_roles:
        raise PermissionDenied("Your account type cannot access this page.")


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not self.allowed_roles:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} must define allowed_roles."
            )
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        _check_role(request.user, self.allowed_roles)
        return super().dispatch(request, *args, **kwargs)


def role_required(*allowed_roles):
    if not allowed_roles:
        raise ImproperlyConfigured("role_required() needs at least one role.")

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            _check_role(request.user, allowed_roles)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
