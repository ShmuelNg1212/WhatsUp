from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from accounts.models import Follow, User
from accounts.permissions import RoleRequiredMixin
from ads.engine import ad_slots, blend, record_impressions, select_feed_ads

from .forms import CommentForm, PostForm
from .models import Like, Post
from .queries import annotated_posts, feed_for, oldest_first_previews, posts_by
from .utils import redirect_back

POSTS_PER_PAGE = 20


class RegularUserRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.REGULAR_USER,)


def paginate_posts(request, queryset):
    page = Paginator(queryset, POSTS_PER_PAGE).get_page(request.GET.get("page"))
    return page, oldest_first_previews(list(page.object_list))


class FeedView(RegularUserRequiredMixin, View):
    """
    The feed (GET) and new-post submission (POST).

    Organic posts with one sponsored ad after every 4th post (ads.engine).
    Served impressions are recorded after the page renders successfully.
    """

    template_name = "posts/feed.html"

    def get(self, request):
        return self.render_feed(PostForm())

    def post(self, request):
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Your post is live.")
            return redirect("posts:feed")
        return self.render_feed(form)

    def render_feed(self, form):
        page, posts = paginate_posts(self.request, feed_for(self.request.user))
        feed_items = blend(posts, select_feed_ads(ad_slots(len(posts))))
        response = render(
            self.request,
            self.template_name,
            {"form": form, "page_obj": page, "posts": posts, "feed_items": feed_items},
        )
        if self.request.method != "HEAD":
            record_impressions(self.request.user, [i.object for i in feed_items if i.is_ad])
        return response


class PostDetailView(RegularUserRequiredMixin, View):
    """One post with every comment and a comment form."""

    def get(self, request, pk):
        post = get_object_or_404(annotated_posts(request.user), pk=pk)
        return render(request, "posts/detail.html", {"post": post, "comment_form": CommentForm()})


class LikeToggleView(RegularUserRequiredMixin, View):
    """POST: like the post, or remove the like if it already exists."""

    http_method_names = ["post"]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
        return redirect_back(request, fallback=post.get_absolute_url())


class CommentCreateView(RegularUserRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
        else:
            messages.error(request, " ".join(form.errors.get("body", ["Invalid comment."])))
        return redirect_back(request, fallback=post.get_absolute_url())


PEOPLE_PER_PAGE = 30


def regular_users_with_counts():
    return User.objects.filter(role=User.Role.REGULAR_USER).annotate(
        follower_count=Count("follower_edges", distinct=True),
        following_count=Count("following_edges", distinct=True),
    )


class ProfileView(RegularUserRequiredMixin, View):
    """A regular user's public profile: counts, follow toggle, and their posts."""

    def get(self, request, username):
        profile_user = get_object_or_404(regular_users_with_counts(), username=username)
        page, posts = paginate_posts(request, posts_by(profile_user, request.user))
        is_following = Follow.objects.filter(
            follower=request.user, following=profile_user
        ).exists()
        return render(
            request,
            "posts/profile.html",
            {
                "profile_user": profile_user,
                "is_following": is_following,
                "is_self": profile_user == request.user,
                "page_obj": page,
                "posts": posts,
            },
        )


class FollowToggleView(RegularUserRequiredMixin, View):
    """POST: follow the user, or unfollow if already following."""

    http_method_names = ["post"]

    def post(self, request, username):
        target = get_object_or_404(User, username=username, role=User.Role.REGULAR_USER)
        fallback = reverse("posts:profile", args=[target.username])
        if target == request.user:
            messages.error(request, "You can't follow yourself.")
            return redirect_back(request, fallback=fallback)
        follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if created:
            messages.success(request, f"You're now following {target.username}.")
        else:
            follow.delete()
            messages.success(request, f"You unfollowed {target.username}.")
        return redirect_back(request, fallback=fallback)


class PeopleView(RegularUserRequiredMixin, View):
    """Discover other regular users to follow."""

    def get(self, request):
        people = (
            regular_users_with_counts()
            .exclude(pk=request.user.pk)
            .annotate(
                followed_by_me=Exists(
                    Follow.objects.filter(follower=request.user, following=OuterRef("pk"))
                )
            )
            .order_by("username")
        )
        page = Paginator(people, PEOPLE_PER_PAGE).get_page(request.GET.get("page"))
        return render(request, "posts/people.html", {"page_obj": page, "people": page.object_list})
