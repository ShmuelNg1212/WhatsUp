from django.urls import path

from . import views

app_name = "ads"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("campaigns/new/", views.CampaignCreateView.as_view(), name="campaign_create"),
    path("campaigns/<int:pk>/", views.CampaignDetailView.as_view(), name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.CampaignUpdateView.as_view(), name="campaign_update"),
    path("campaigns/<int:pk>/delete/", views.CampaignDeleteView.as_view(), name="campaign_delete"),
]
