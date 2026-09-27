from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("posts/<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path("posts/<int:pk>/like/", views.LikeToggleView.as_view(), name="like"),
    path("posts/<int:pk>/comments/", views.CommentCreateView.as_view(), name="comment"),
]
