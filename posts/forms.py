from django import forms
from django.template.defaultfilters import filesizeformat

from .models import Comment, Post

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("body", "image")
        labels = {"body": "", "image": "Add an image (optional)"}
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "What's up?"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > MAX_IMAGE_BYTES:
            raise forms.ValidationError(
                f"Images must be {filesizeformat(MAX_IMAGE_BYTES)} or smaller "
                f"(this one is {filesizeformat(image.size)})."
            )
        return image


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        labels = {"body": ""}
        widgets = {"body": forms.TextInput(attrs={"placeholder": "Write a comment…"})}
