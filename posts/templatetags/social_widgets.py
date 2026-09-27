"""
Right-rail widgets for the social layout. Load with {% load social_widgets %}.

Each widget is a single bounded query (LIMIT n), so every social page gets a
constant +2 queries (pinned in posts/tests/test_queries.py).
"""

from datetime import timedelta

from django import template
from django.db.models import Count
from django.utils import timezone

from accounts.models import Follow, User
from posts.models import Post

register = template.Library()

TRENDING_WINDOW = timedelta(days=7)


def _widget_context(context, **extra):
    # Inclusion tags get a fresh context; pass what forms and links need.
    return {"request": context["request"], "csrf_token": context.get("csrf_token"), "user": context.get("user"), **extra}


@register.inclusion_tag("posts/widgets/who_to_follow.html", takes_context=True)
def who_to_follow(context, limit=3):
    """Regular users the viewer doesn't follow yet (not themselves), most-followed first."""
    viewer = context["request"].user
    suggestions = (
        User.objects.filter(role=User.Role.REGULAR_USER)
        .exclude(pk=viewer.pk)
        .exclude(pk__in=Follow.objects.filter(follower=viewer).values("following_id"))
        .annotate(follower_count=Count("follower_edges"))
        .order_by("-follower_count", "username")[:limit]
    )
    return _widget_context(context, suggestions=list(suggestions))


@register.inclusion_tag("posts/widgets/trending.html", takes_context=True)
def trending_posts(context, limit=3):
    """Most-liked posts from the last 7 days (at least one like)."""
    posts = (
        Post.objects.filter(created_at__gte=timezone.now() - TRENDING_WINDOW)
        .annotate(like_count=Count("likes"))
        .filter(like_count__gt=0)
        .select_related("author")
        .order_by("-like_count", "-created_at")[:limit]
    )
    return _widget_context(context, posts=list(posts))
