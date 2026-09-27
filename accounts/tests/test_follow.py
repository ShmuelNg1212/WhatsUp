from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Follow

from .helpers import make_advertiser, make_regular


class FollowModelTests(TestCase):
    def setUp(self):
        self.alice = make_regular("alice")
        self.bob = make_regular("bob")

    def test_follow_is_asymmetric(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertIn(self.bob, self.alice.following.all())
        self.assertIn(self.alice, self.bob.followers.all())
        self.assertNotIn(self.alice, self.bob.following.all())
        self.assertNotIn(self.bob, self.alice.followers.all())

    def test_m2m_add_and_remove_manage_follow_rows(self):
        self.alice.following.add(self.bob)
        self.assertTrue(Follow.objects.filter(follower=self.alice, following=self.bob).exists())
        self.alice.following.remove(self.bob)
        self.assertFalse(Follow.objects.exists())

    def test_counts(self):
        carol = make_regular("carol")
        self.alice.following.add(self.bob, carol)
        carol.following.add(self.alice)
        self.assertEqual(self.alice.following.count(), 2)
        self.assertEqual(self.alice.followers.count(), 1)

    def test_database_rejects_duplicate_follow(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Follow.objects.create(follower=self.alice, following=self.bob)

    def test_database_rejects_self_follow(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Follow.objects.create(follower=self.alice, following=self.alice)

    def test_full_clean_rejects_self_follow(self):
        with self.assertRaises(ValidationError):
            Follow(follower=self.alice, following=self.alice).full_clean()

    def test_full_clean_rejects_following_an_advertiser(self):
        follow = Follow(follower=self.alice, following=make_advertiser())
        with self.assertRaises(ValidationError) as ctx:
            follow.full_clean()
        self.assertIn("following", ctx.exception.message_dict)

    def test_full_clean_rejects_advertiser_as_follower(self):
        follow = Follow(follower=make_advertiser(), following=self.alice)
        with self.assertRaises(ValidationError) as ctx:
            follow.full_clean()
        self.assertIn("follower", ctx.exception.message_dict)

    def test_follows_deleted_with_user(self):
        self.alice.following.add(self.bob)
        self.bob.delete()
        self.assertFalse(Follow.objects.exists())

    def test_str(self):
        follow = Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertEqual(str(follow), "alice → bob")
