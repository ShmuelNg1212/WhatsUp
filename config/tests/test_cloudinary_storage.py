"""
Contract test for the (unmaintained) django-cloudinary-storage backend on this Django version:
an ImageField upload goes through MediaCloudinaryStorage and yields a Cloudinary URL.
The Cloudinary API is mocked, so no network access is needed.
"""

import os
from unittest import mock

from django.test import TestCase, override_settings

from accounts.tests.helpers import make_regular
from posts.models import Post
from posts.tests.utils import make_image

CLOUDINARY_URL = "cloudinary://123456:secret@demo-cloud"
CLOUDINARY_STORAGES = {
    "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class CloudinaryMediaStorageContractTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._env = mock.patch.dict(os.environ, {"CLOUDINARY_URL": CLOUDINARY_URL})
        cls._env.start()
        import cloudinary

        cloudinary.reset_config()  # pick up CLOUDINARY_URL from the patched environment
        import cloudinary_storage.storage  # noqa: F401  (raises if credentials are missing)

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()
        super().tearDownClass()

    @override_settings(STORAGES=CLOUDINARY_STORAGES)
    def test_image_upload_goes_to_cloudinary(self):
        def fake_upload(content, **options):
            fake_upload.options = options
            fake_upload.body = content.read()
            return {"public_id": f"{options['folder']}/cat"}

        with mock.patch("cloudinary.uploader.upload", side_effect=fake_upload) as upload:
            post = Post.objects.create(author=make_regular(), body="hi", image=make_image("cat.png"))

        upload.assert_called_once()
        self.assertTrue(fake_upload.body.startswith(b"\x89PNG"))
        self.assertEqual(fake_upload.options["resource_type"], "image")
        self.assertTrue(fake_upload.options["folder"].endswith(post.created_at.strftime("posts/%Y/%m")))
        self.assertEqual(post.image.name, f"{fake_upload.options['folder']}/cat")
        url = post.image.url
        self.assertTrue(url.startswith("https://res.cloudinary.com/demo-cloud/image/upload/"), url)
        self.assertTrue(url.endswith("/cat"), url)

    @override_settings(STORAGES=CLOUDINARY_STORAGES)
    def test_rendered_feed_uses_cloudinary_urls(self):
        with mock.patch("cloudinary.uploader.upload", return_value={"public_id": "media/posts/2026/09/pic"}):
            post = Post.objects.create(author=make_regular("alice"), body="pic", image=make_image())
        self.client.force_login(post.author)
        response = self.client.get("/feed/")
        self.assertContains(response, 'src="https://res.cloudinary.com/demo-cloud/image/upload/')
