import os

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.tests.helpers import make_regular
from posts.models import COMMENT_MAX_LENGTH, POST_MAX_LENGTH, Comment, Like, Post

from .utils import TempMediaMixin, add_comment, add_like, make_image, make_post


class PostModelTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.alice = make_regular("alice")

    def test_text_only_post(self):
        post = make_post(self.alice, "Just text")
        self.assertFalse(post.image)
        self.assertEqual(self.alice.posts.get(), post)

    def test_post_with_image_is_stored_under_media_root(self):
        post = make_post(self.alice, "With pic", image=make_image())
        self.assertTrue(post.image.name.startswith("posts/"))
        self.assertTrue(os.path.exists(post.image.path))

    def test_database_rejects_empty_body(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Post.objects.create(author=self.alice, body="")

    def test_full_clean_rejects_too_long_body(self):
        post = Post(author=self.alice, body="x" * (POST_MAX_LENGTH + 1))
        with self.assertRaises(ValidationError) as ctx:
            post.full_clean()
        self.assertIn("body", ctx.exception.message_dict)

    def test_default_ordering_is_newest_first(self):
        first = make_post(self.alice, "first")
        second = make_post(self.alice, "second")
        self.assertEqual(list(Post.objects.all()), [second, first])

    def test_posts_deleted_with_author(self):
        make_post(self.alice)
        self.alice.delete()
        self.assertFalse(Post.objects.exists())


class LikeModelTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        self.post = make_post(self.alice)

    def test_user_can_like_a_post(self):
        add_like(self.bob, self.post)
        self.assertEqual(self.post.likes.count(), 1)

    def test_user_can_like_own_post(self):
        add_like(self.alice, self.post)
        self.assertEqual(self.post.likes.count(), 1)

    def test_database_rejects_second_like_by_same_user(self):
        add_like(self.bob, self.post)
        with self.assertRaises(IntegrityError), transaction.atomic():
            add_like(self.bob, self.post)

    def test_full_clean_reports_duplicate_like(self):
        add_like(self.bob, self.post)
        with self.assertRaises(ValidationError):
            Like(user=self.bob, post=self.post).full_clean()

    def test_different_users_can_like_same_post(self):
        add_like(self.alice, self.post)
        add_like(self.bob, self.post)
        self.assertEqual(self.post.likes.count(), 2)

    def test_likes_deleted_with_post(self):
        add_like(self.bob, self.post)
        self.post.delete()
        self.assertFalse(Like.objects.exists())


class CommentModelTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")
        self.post = make_post(self.alice)

    def test_comment_belongs_to_post_and_author(self):
        comment = add_comment(self.bob, self.post, "Great post")
        self.assertEqual(self.post.comments.get(), comment)
        self.assertEqual(self.bob.comments.get(), comment)

    def test_comments_are_ordered_oldest_first(self):
        first = add_comment(self.bob, self.post, "first")
        second = add_comment(self.alice, self.post, "second")
        self.assertEqual(list(self.post.comments.all()), [first, second])

    def test_database_rejects_empty_comment(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Comment.objects.create(author=self.bob, post=self.post, body="")

    def test_full_clean_rejects_too_long_comment(self):
        comment = Comment(author=self.bob, post=self.post, body="x" * (COMMENT_MAX_LENGTH + 1))
        with self.assertRaises(ValidationError):
            comment.full_clean()

    def test_comments_deleted_with_post(self):
        add_comment(self.bob, self.post)
        self.post.delete()
        self.assertFalse(Comment.objects.exists())
