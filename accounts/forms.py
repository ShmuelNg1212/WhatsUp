from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from ads.models import AdvertiserProfile

from .models import User


class RegularSignupForm(UserCreationForm):
    role = User.Role.REGULAR_USER

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        # Set before validation so model constraints see the final role.
        self.instance.role = self.role

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email


class AdvertiserSignupForm(RegularSignupForm):
    role = User.Role.ADVERTISER

    company_name = forms.CharField(max_length=200)
    website = forms.URLField(required=False, assume_scheme="https")

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("AdvertiserSignupForm must save the user and profile together.")
        user = super().save(commit=True)
        profile = AdvertiserProfile(
            user=user,
            company_name=self.cleaned_data["company_name"],
            website=self.cleaned_data["website"],
        )
        profile.full_clean()
        profile.save()
        return user
