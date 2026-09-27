"""Validators shared by several apps. `core` is a plain package, not a Django app."""

from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image_size(image):
    if image and image.size > MAX_IMAGE_BYTES:
        raise ValidationError(
            f"Images must be {filesizeformat(MAX_IMAGE_BYTES)} or smaller "
            f"(this one is {filesizeformat(image.size)})."
        )
