"""
Query builders for lists of posts.

Every page that shows post cards (feed, profile, post detail) goes through
`annotated_posts()`, so each page runs a fixed number of queries however
many posts, likes, or comments it shows. `posts/tests/test_queries.py`
locks the query counts in place.
"""

from django.db.models import Count, Exists, OuterRef, Prefetch, Q

from accounts.models import Follow

from .models import Comment, Like, Post

FEED_COMMENT_PREVIEW = 3


def annotated_posts(viewer, comment_limit=None):
    """
    Posts with the author joined in and, computed in SQL:
    like_count, comment_count, liked_by_me.

    Comments are prefetched into `post.shown_comments` (oldest first) in one
    extra query. With `comment_limit`, only the latest N per post are loaded
    (sliced prefetch, which uses window functions).
    """
    comments = Comment.objects.select_related("author")
    if comment_limit:
        comments = comments.order_by("-created_at", "-id")[:comment_limit]
    else:
        comments = comments.order_by("created_at", "id")

    return (
        Post.objects.select_related("author")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
            liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=viewer)),
        )
        .prefetch_related(Prefetch("comments", queryset=comments, to_attr="shown_comments"))
        .order_by("-created_at", "-id")
    )


def feed_for(user):
    """The organic feed: the user's own posts plus posts from everyone they follow."""
    followed_ids = Follow.objects.filter(follower=user).values("following_id")
    return annotated_posts(user, comment_limit=FEED_COMMENT_PREVIEW).filter(
        Q(author=user) | Q(author_id__in=followed_ids)
    )


def posts_by(author, viewer):
    """An author's posts as seen by `viewer` (for profile pages)."""
    return annotated_posts(viewer, comment_limit=FEED_COMMENT_PREVIEW).filter(author=author)


def oldest_first_previews(posts):
    """
    Comment previews from feed_for() / posts_by() are loaded newest-first
    (needed to slice the *latest* N). Flip them in place for display.
    """
    for post in posts:
        post.shown_comments.reverse()
    return posts
