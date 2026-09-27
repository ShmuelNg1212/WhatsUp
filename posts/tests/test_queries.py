"""
Every social page also renders the right-rail widgets (posts/templatetags/social_widgets.py):
+2 constant queries (who_to_follow, trending_posts), included in the numbers below.

N+1 guards: each page must run the same number of queries no matter how much
content it shows. If one of these tests fails, a template or view has started
triggering a query per post, like, or comment.
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Follow
from accounts.tests.helpers import make_regular

from .utils import TempMediaMixin, add_comment, add_like, make_image, make_post

# session + user + paginator COUNT + posts (author, counts, liked_by_me joined in) + comment previews
# + eligible-ad lookup (runs because the page has >= 4 posts; no ads exist in this test).
# The with-ads cases are pinned in ads/tests/test_feed_queries.py.
FEED_QUERIES = 8
# session + user + profile user (with counts) + paginator COUNT + posts + comment previews + is_following
PROFILE_QUERIES = 9
# session + user + post (with counts) + all comments
DETAIL_QUERIES = 6
# session + user + paginator COUNT + people (with counts and followed_by_me)
PEOPLE_QUERIES = 6


class QueryCountTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.viewer = make_regular("viewer")
        self.friends = [make_regular(f"friend{i}") for i in range(4)]
        for friend in self.friends:
            Follow.objects.create(follower=self.viewer, following=friend)
        self.client.force_login(self.viewer)

    def populate(self, posts_per_author):
        """Create posts with images, likes, and comments by many different users."""
        people = [self.viewer, *self.friends]
        for author in people:
            for i in range(posts_per_author):
                post = make_post(author, f"{author.username} #{i}", image=make_image())
                for j, person in enumerate(people):
                    add_like(person, post)
                    add_comment(person, post, f"comment {j}")

    def count_queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def assert_constant(self, url, expected):
        self.populate(posts_per_author=1)
        small = self.count_queries(url)
        self.populate(posts_per_author=3)
        large = self.count_queries(url)
        self.assertEqual(small, large, f"{url}: query count grew with content ({small} → {large})")
        self.assertEqual(large, expected, f"{url}: expected {expected} queries, got {large}")

    def test_feed(self):
        self.assert_constant(reverse("posts:feed"), FEED_QUERIES)

    def test_profile(self):
        self.assert_constant(reverse("posts:profile", args=["friend0"]), PROFILE_QUERIES)

    def test_people(self):
        self.assert_constant(reverse("posts:people"), PEOPLE_QUERIES)

    def test_post_detail(self):
        post = make_post(self.friends[0], "detail")
        url = post.get_absolute_url()
        few = self.count_queries(url)
        for person in [self.viewer, *self.friends]:
            add_like(person, post)
            for i in range(5):
                add_comment(person, post, f"c{i}")
        many = self.count_queries(url)
        self.assertEqual(few, many)
        self.assertEqual(many, DETAIL_QUERIES)
