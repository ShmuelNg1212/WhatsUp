from django.views.generic import TemplateView

from accounts.models import User
from accounts.permissions import RoleRequiredMixin


class FeedView(RoleRequiredMixin, TemplateView):
    """The regular user's home feed. Posts arrive in Phase 2."""

    allowed_roles = (User.Role.REGULAR_USER,)
    template_name = "posts/feed.html"
