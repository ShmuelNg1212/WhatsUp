from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User


class UserRoleTests(TestCase):
    def test_default_role_is_regular_user(self):
        user = User.objects.create_user("alice", "alice@example.com", "pw-12345!")
        self.assertEqual(user.role, User.Role.REGULAR_USER)

    def test_role_helpers_for_regular_user(self):
        user = User.objects.create_user("alice", "alice@example.com", "pw-12345!")
        self.assertTrue(user.is_regular_user)
        self.assertFalse(user.is_advertiser)

    def test_role_helpers_for_advertiser(self):
        user = User.objects.create_user(
            "acme", "ads@acme.com", "pw-12345!", role=User.Role.ADVERTISER
        )
        self.assertTrue(user.is_advertiser)
        self.assertFalse(user.is_regular_user)

    def test_role_choices_are_exactly_regular_and_advertiser(self):
        self.assertEqual(set(User.Role.values), {"REGULAR_USER", "ADVERTISER"})

    def test_database_rejects_unknown_role(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("mallory", "m@example.com", "pw-12345!", role="ADMIN")

    def test_database_rejects_unknown_role_via_bulk_update(self):
        User.objects.create_user("alice", "alice@example.com", "pw-12345!")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.update(role="SUPERHERO")

    def test_full_clean_rejects_unknown_role(self):
        user = User(username="mallory", email="m@example.com", role="ADMIN")
        user.set_password("pw-12345!")
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn("role", ctx.exception.message_dict)


class UserEmailTests(TestCase):
    def test_email_is_required_by_validation(self):
        user = User(username="noemail")
        user.set_password("pw-12345!")
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn("email", ctx.exception.message_dict)

    def test_email_is_a_required_field_for_createsuperuser(self):
        self.assertIn("email", User.REQUIRED_FIELDS)

    def test_database_rejects_duplicate_email_ignoring_case(self):
        User.objects.create_user("alice", "Alice@Example.com", "pw-12345!")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("alice2", "alice@example.com", "pw-12345!")

    def test_full_clean_reports_duplicate_email(self):
        User.objects.create_user("alice", "alice@example.com", "pw-12345!")
        dup = User(username="alice2", email="ALICE@example.com")
        dup.set_password("pw-12345!")
        with self.assertRaises(ValidationError) as ctx:
            dup.full_clean()
        self.assertIn("A user with that email already exists.", str(ctx.exception))

    def test_username_is_unique(self):
        User.objects.create_user("alice", "a1@example.com", "pw-12345!")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("alice", "a2@example.com", "pw-12345!")


class SuperuserTests(TestCase):
    def test_create_superuser(self):
        admin = User.objects.create_superuser("root", "root@example.com", "pw-12345!")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.role, User.Role.REGULAR_USER)
