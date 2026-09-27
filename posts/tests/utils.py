import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from posts.models import Comment, Like, Post


def make_image(name="photo.png", size=(10, 10), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, "purple").save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


def make_post(author, body="Hello world", **kwargs):
    return Post.objects.create(author=author, body=body, **kwargs)


def add_like(user, post):
    return Like.objects.create(user=user, post=post)


def add_comment(author, post, body="Nice!"):
    return Comment.objects.create(author=author, post=post, body=body)


class TempMediaMixin:
    """Route uploads to a throwaway directory so tests never touch media/."""

    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.mkdtemp(prefix="whatsup-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
