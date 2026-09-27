from django.test import TestCase
from django.urls import reverse

from accounts.models import Follow
from accounts.tests.helpers import make_advertiser, make_regular
from core.validators import MAX_IMAGE_BYTES
from posts.models import Comment, Like, Post
from posts.views import POSTS_PER_PAGE

from .utils import TempMediaMixin, add_comment, add_like, make_image, make_post

FEED = reverse("posts:feed")


def profile_url(user):
    return reverse("posts:profile", args=[user.username])


class FeedMembershipTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        self.carol = make_regular("carol")
        self.client.force_login(self.alice)

    def feed_posts(self, **params):
        return list(self.client.get(FEED, params).context["posts"])

    def test_empty_feed_shows_empty_state(self):
        response = self.client.get(FEED)
        self.assertContains(response, "Your feed is empty.")

    def test_includes_own_posts(self):
        mine = make_post(self.alice, "mine")
        self.assertEqual(self.feed_posts(), [mine])

    def test_includes_followed_users_posts(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        bobs = make_post(self.bob, "from bob")
        self.assertEqual(self.feed_posts(), [bobs])

    def test_excludes_unfollowed_users_posts(self):
        make_post(self.carol, "from carol")
        self.assertEqual(self.feed_posts(), [])

    def test_follow_is_one_way(self):
        Follow.objects.create(follower=self.bob, following=self.alice)
        make_post(self.bob, "bob follows alice, not vice versa")
        self.assertEqual(self.feed_posts(), [])

    def test_unfollowing_removes_posts(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        make_post(self.bob)
        Follow.objects.all().delete()
        self.assertEqual(self.feed_posts(), [])

    def test_reverse_chronological_order_across_authors(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        p1 = make_post(self.alice, "1")
        p2 = make_post(self.bob, "2")
        p3 = make_post(self.alice, "3")
        self.assertEqual(self.feed_posts(), [p3, p2, p1])

    def test_pagination(self):
        for i in range(POSTS_PER_PAGE + 5):
            make_post(self.alice, f"post {i}")
        page1 = self.feed_posts()
        page2 = self.feed_posts(page=2)
        self.assertEqual(len(page1), POSTS_PER_PAGE)
        self.assertEqual(len(page2), 5)
        self.assertEqual(page1[0].body, f"post {POSTS_PER_PAGE + 4}")
        self.assertEqual(page2[-1].body, "post 0")

    def test_counts_and_liked_by_me_annotations(self):
        post = make_post(self.alice)
        add_like(self.bob, post)
        add_like(self.carol, post)
        add_comment(self.bob, post)
        [shown] = self.feed_posts()
        self.assertEqual(shown.like_count, 2)
        self.assertEqual(shown.comment_count, 1)
        self.assertFalse(shown.liked_by_me)
        add_like(self.alice, post)
        self.assertTrue(self.feed_posts()[0].liked_by_me)

    def test_feed_previews_latest_three_comments_oldest_first(self):
        post = make_post(self.alice)
        for i in range(5):
            add_comment(self.bob, post, f"c{i}")
        response = self.client.get(FEED)
        [shown] = response.context["posts"]
        self.assertEqual([c.body for c in shown.shown_comments], ["c2", "c3", "c4"])
        self.assertContains(response, "View all 5 comments")


class PostCreateTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.client.force_login(self.alice)

    def test_create_text_post(self):
        response = self.client.post(FEED, {"body": "Hello!"})
        self.assertRedirects(response, FEED)
        post = Post.objects.get()
        self.assertEqual((post.author, post.body), (self.alice, "Hello!"))
        self.assertContains(self.client.get(FEED), "Hello!")

    def test_create_post_with_image(self):
        self.client.post(FEED, {"body": "Look", "image": make_image("cat.png")})
        post = Post.objects.get()
        self.assertTrue(post.image.name.startswith("posts/"))
        self.assertContains(self.client.get(FEED), post.image.url)

    def test_author_cannot_be_spoofed(self):
        bob = make_regular("bob")
        self.client.post(FEED, {"body": "Hi", "author": bob.pk})
        self.assertEqual(Post.objects.get().author, self.alice)

    def test_empty_body_rejected(self):
        response = self.client.post(FEED, {"body": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertIn("body", response.context["form"].errors)
        self.assertFalse(Post.objects.exists())

    def test_too_long_body_rejected(self):
        response = self.client.post(FEED, {"body": "x" * 2001})
        self.assertIn("body", response.context["form"].errors)

    def test_non_image_file_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("evil.png", b"not an image", content_type="image/png")
        response = self.client.post(FEED, {"body": "Hi", "image": fake})
        self.assertIn("image", response.context["form"].errors)
        self.assertFalse(Post.objects.exists())

    def test_oversized_image_rejected(self):
        from unittest import mock

        with mock.patch("core.validators.MAX_IMAGE_BYTES", 10):
            response = self.client.post(FEED, {"body": "Hi", "image": make_image()})
        self.assertIn("image", response.context["form"].errors)
        self.assertFalse(Post.objects.exists())

    def test_image_limit_is_five_megabytes(self):
        self.assertEqual(MAX_IMAGE_BYTES, 5 * 1024 * 1024)


class LikeToggleTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.post = make_post(make_regular("bob"))
        self.url = reverse("posts:like", args=[self.post.pk])
        self.client.force_login(self.alice)

    def test_like_then_unlike(self):
        self.client.post(self.url)
        self.assertTrue(Like.objects.filter(user=self.alice, post=self.post).exists())
        self.client.post(self.url)
        self.assertFalse(Like.objects.exists())

    def test_redirects_to_safe_next(self):
        response = self.client.post(self.url, {"next": f"/feed/#post-{self.post.pk}"})
        self.assertEqual(response["Location"], f"/feed/#post-{self.post.pk}")

    def test_ignores_external_next(self):
        response = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertRedirects(response, self.post.get_absolute_url())

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(Like.objects.exists())

    def test_missing_post_is_404(self):
        self.assertEqual(self.client.post(reverse("posts:like", args=[999])).status_code, 404)

    def test_like_button_reflects_state(self):
        self.client.post(self.url)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, 'data-testid="like-button" data-liked="true"')
        self.assertContains(response, 'data-testid="like-count">1<')


class CommentTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.post = make_post(make_regular("bob"))
        self.url = reverse("posts:comment", args=[self.post.pk])
        self.client.force_login(self.alice)

    def test_add_comment(self):
        response = self.client.post(self.url, {"body": "Nice one"})
        self.assertRedirects(response, self.post.get_absolute_url())
        comment = Comment.objects.get()
        self.assertEqual((comment.author, comment.post, comment.body), (self.alice, self.post, "Nice one"))

    def test_empty_comment_rejected_with_message(self):
        response = self.client.post(self.url, {"body": ""}, follow=True)
        self.assertFalse(Comment.objects.exists())
        self.assertContains(response, "This field is required.")

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class PostDetailTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.post = make_post(self.alice, "The post")
        self.client.force_login(make_regular("bob"))

    def test_url(self):
        self.assertEqual(self.post.get_absolute_url(), f"/posts/{self.post.pk}/")

    def test_shows_all_comments_oldest_first(self):
        for i in range(5):
            add_comment(self.alice, self.post, f"c{i}")
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual([c.body for c in response.context["post"].shown_comments], [f"c{i}" for i in range(5)])

    def test_any_regular_user_can_view_any_post(self):
        self.assertContains(self.client.get(self.post.get_absolute_url()), "The post")

    def test_missing_post_is_404(self):
        self.assertEqual(self.client.get("/posts/999/").status_code, 404)


class ProfileTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        self.client.force_login(self.alice)

    def test_shows_counts_and_only_that_users_posts(self):
        make_post(self.bob, "bob post")
        make_post(self.alice, "alice post")
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.bob, following=make_regular("carol"))
        response = self.client.get(profile_url(self.bob))
        self.assertEqual(response.context["profile_user"].follower_count, 1)
        self.assertEqual(response.context["profile_user"].following_count, 1)
        self.assertEqual([p.body for p in response.context["posts"]], ["bob post"])
        self.assertContains(response, 'data-testid="post-count">1<')

    def test_shows_follow_button_when_not_following(self):
        response = self.client.get(profile_url(self.bob))
        self.assertFalse(response.context["is_following"])
        self.assertContains(response, 'data-testid="profile-follow-button" data-following="false"')

    def test_shows_unfollow_button_when_following(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertContains(
            self.client.get(profile_url(self.bob)),
            'data-testid="profile-follow-button" data-following="true"',
        )

    def test_own_profile_has_no_follow_button(self):
        response = self.client.get(profile_url(self.alice))
        self.assertContains(response, "This is you")
        # Other users' follow buttons (e.g. suggestions) may appear; the profile header must not have one.
        self.assertNotContains(response, 'data-testid="profile-follow-button"')

    def test_unknown_user_is_404(self):
        self.assertEqual(self.client.get("/u/nobody/").status_code, 404)

    def test_advertisers_have_no_profile(self):
        self.assertEqual(self.client.get(profile_url(make_advertiser())).status_code, 404)


class FollowToggleTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        self.url = reverse("posts:follow", args=["bob"])
        self.client.force_login(self.alice)

    def test_follow_then_unfollow(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, profile_url(self.bob))
        self.assertIn(self.bob, self.alice.following.all())
        self.client.post(self.url)
        self.assertNotIn(self.bob, self.alice.following.all())

    def test_updates_follower_count_on_profile(self):
        self.client.post(self.url)
        response = self.client.get(profile_url(self.bob))
        self.assertContains(response, 'data-testid="follower-count">1<')

    def test_cannot_follow_self(self):
        response = self.client.post(reverse("posts:follow", args=["alice"]), follow=True)
        self.assertFalse(Follow.objects.exists())
        self.assertContains(response, "You can&#x27;t follow yourself.")

    def test_cannot_follow_advertiser(self):
        advertiser = make_advertiser("acme")
        response = self.client.post(reverse("posts:follow", args=[advertiser.username]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Follow.objects.exists())

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_honours_safe_next(self):
        response = self.client.post(self.url, {"next": "/people/"})
        self.assertEqual(response["Location"], "/people/")


class PeopleTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        make_advertiser("acme")
        self.client.force_login(self.alice)

    def test_lists_other_regular_users_only(self):
        response = self.client.get(reverse("posts:people"))
        self.assertEqual([p.username for p in response.context["people"]], ["bob"])

    def test_marks_who_i_follow(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        response = self.client.get(reverse("posts:people"))
        self.assertTrue(response.context["people"][0].followed_by_me)
        self.assertContains(response, 'data-testid="follow-button" data-following="true"')


class SocialGatingTests(TestCase):
    """Every social route: anonymous → login, advertiser → 403, regular → allowed."""

    def setUp(self):
        self.bob = make_regular("bob")
        post = make_post(self.bob)
        self.get_routes = [
            FEED,
            reverse("posts:people"),
            profile_url(self.bob),
            post.get_absolute_url(),
        ]
        self.post_routes = [
            FEED,
            reverse("posts:like", args=[post.pk]),
            reverse("posts:comment", args=[post.pk]),
            reverse("posts:follow", args=["bob"]),
        ]

    def test_anonymous_redirected_to_login(self):
        for url in self.get_routes:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
        for url in self.post_routes:
            with self.subTest(url=url, method="POST"):
                response = self.client.post(url, {"body": "x"})
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("login")))

    def test_advertiser_forbidden(self):
        self.client.force_login(make_advertiser())
        for url in self.get_routes:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in self.post_routes:
            with self.subTest(url=url, method="POST"):
                self.assertEqual(self.client.post(url, {"body": "x"}).status_code, 403)
        self.assertEqual(Post.objects.count(), 1)
        self.assertFalse(Like.objects.exists())
        self.assertFalse(Comment.objects.exists())
        self.assertFalse(Follow.objects.exists())

    def test_regular_user_allowed(self):
        self.client.force_login(make_regular("alice"))
        for url in self.get_routes:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class NavigationTests(TestCase):
    def test_regular_user_nav_links(self):
        alice = make_regular("alice")
        self.client.force_login(alice)
        response = self.client.get(FEED)
        for url in (FEED, reverse("posts:people"), profile_url(alice)):
            self.assertContains(response, f'href="{url}"')

    def test_advertiser_nav_has_no_social_links(self):
        self.client.force_login(make_advertiser())
        response = self.client.get(reverse("ads:dashboard"))
        self.assertNotContains(response, f'href="{reverse("posts:people")}"')
