from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("feed/", views.FeedView.as_view(), name="feed"),
]
