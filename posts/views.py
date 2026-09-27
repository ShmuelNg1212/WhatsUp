from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views import View

from accounts.models import User
from accounts.permissions import RoleRequiredMixin

from .forms import PostForm
from .queries import feed_for, oldest_first_previews

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
