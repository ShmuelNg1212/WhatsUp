from accounts.models import User
from ads.models import AdvertiserProfile

PASSWORD = "Str0ng-pass-99"


def make_regular(username="alice"):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD)


def make_advertiser(username="acme", company_name="Acme Inc."):
    user = User.objects.create_user(
        username, f"{username}@example.com", PASSWORD, role=User.Role.ADVERTISER
    )
    AdvertiserProfile.objects.create(user=user, company_name=company_name)
    return user
