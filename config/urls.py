from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="landing.html"), name="home"),
    path("accounts/", include("accounts.urls")),
    path("admin/", admin.site.urls),
]
