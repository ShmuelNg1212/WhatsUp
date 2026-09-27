from django.urls import path

from . import views

app_name = "ads"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("click/<int:ad_id>/", views.AdClickView.as_view(), name="click"),
    path("campaigns/new/", views.CampaignCreateView.as_view(), name="campaign_create"),
    path("campaigns/<int:pk>/", views.CampaignDetailView.as_view(), name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.CampaignUpdateView.as_view(), name="campaign_update"),
    path("campaigns/<int:pk>/delete/", views.CampaignDeleteView.as_view(), name="campaign_delete"),
    path(
        "campaigns/<int:campaign_pk>/units/new/",
        views.AdUnitCreateView.as_view(),
        name="adunit_create",
    ),
    path(
        "campaigns/<int:campaign_pk>/units/<int:pk>/edit/",
        views.AdUnitUpdateView.as_view(),
        name="adunit_update",
    ),
    path(
        "campaigns/<int:campaign_pk>/units/<int:pk>/delete/",
        views.AdUnitDeleteView.as_view(),
        name="adunit_delete",
    ),
]
