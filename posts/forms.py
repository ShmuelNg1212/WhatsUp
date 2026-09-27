from django import forms

from core.validators import validate_image_size

from .models import Comment, Post


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
        validate_image_size(image)
        return image


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        labels = {"body": ""}
        widgets = {"body": forms.TextInput(attrs={"placeholder": "Write a comment…"})}
