from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("posts/<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path("posts/<int:pk>/like/", views.LikeToggleView.as_view(), name="like"),
    path("posts/<int:pk>/comments/", views.CommentCreateView.as_view(), name="comment"),
    path("people/", views.PeopleView.as_view(), name="people"),
    path("u/<str:username>/", views.ProfileView.as_view(), name="profile"),
    path("u/<str:username>/follow/", views.FollowToggleView.as_view(), name="follow"),
]
