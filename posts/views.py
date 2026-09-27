from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.models import User
from accounts.permissions import RoleRequiredMixin

from .forms import CommentForm, PostForm
from .models import Like, Post
from .queries import annotated_posts, feed_for, oldest_first_previews
from .utils import redirect_back

POSTS_PER_PAGE = 20


class RegularUserRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.REGULAR_USER,)


def paginate_posts(request, queryset):
    page = Paginator(queryset, POSTS_PER_PAGE).get_page(request.GET.get("page"))
    return page, oldest_first_previews(list(page.object_list))


class FeedView(RegularUserRequiredMixin, View):
    """The organic feed (GET) and new-post submission (POST)."""

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
        return render(
            self.request,
            self.template_name,
            {"form": form, "page_obj": page, "posts": posts},
        )


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
