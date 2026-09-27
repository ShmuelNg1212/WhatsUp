from django import forms
from django.utils import timezone

from core.validators import validate_image_size

from .models import AdUnit, Campaign


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class CampaignForm(forms.ModelForm):
    """
    `advertiser` is deliberately not a field. The view passes the owner in,
    and it is used for the per-advertiser unique-name check.
    """

    class Meta:
        model = Campaign
        fields = ("name", "budget", "start_date", "end_date", "status")
        widgets = {
            "start_date": DateInput(),
            "end_date": DateInput(),
            "budget": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }
        help_texts = {
            "status": "Only Active campaigns within their dates will be eligible to serve.",
        }

    def __init__(self, *args, advertiser, **kwargs):
        super().__init__(*args, **kwargs)
        self.advertiser = advertiser

    @property
    def is_new(self):
        return self.instance.pk is None

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Campaign.objects.filter(advertiser=self.advertiser, name__iexact=name)
        if not self.is_new:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("You already have a campaign with this name.")
        return name

    def clean_start_date(self):
        start = self.cleaned_data["start_date"]
        if self.is_new and start < timezone.localdate():
            raise forms.ValidationError("A new campaign can't start in the past.")
        return start

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date can't be before the start date.")
        return cleaned


class AdUnitForm(forms.ModelForm):
    """`campaign` is deliberately not a field. The view sets it from the URL after checking ownership."""

    target_url = forms.URLField(
        label="Target URL",
        max_length=500,
        assume_scheme="https",
        help_text="Where people go when they click the ad (http or https).",
    )

    class Meta:
        model = AdUnit
        fields = ("headline", "body", "image", "target_url")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        validate_image_size(image)
        return image
