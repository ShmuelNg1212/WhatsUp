from django.shortcuts import render

from accounts.models import User
from accounts.permissions import role_required


@role_required(User.Role.ADVERTISER)
def dashboard(request):
    """The advertiser's home. Campaigns and ad units arrive in a later phase."""
    profile = getattr(request.user, "advertiser_profile", None)
    return render(request, "ads/dashboard.html", {"profile": profile})
