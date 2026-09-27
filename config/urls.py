from django.contrib import admin
from django.urls import include, path

from accounts.views import home

urlpatterns = [
    path("", home, name="home"),
    path("accounts/", include("accounts.urls")),
    path("feed/", include("posts.urls")),
    path("ads/", include("ads.urls")),
    path("admin/", admin.site.urls),
]
