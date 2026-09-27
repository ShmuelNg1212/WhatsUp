from django.contrib.auth import login
from django.shortcuts import redirect
from django.views.generic import CreateView

from .forms import AdvertiserSignupForm, RegularSignupForm


class SignupView(CreateView):
    form_class = RegularSignupForm
    template_name = "accounts/signup.html"
    extra_context = {"heading": "Create your account", "account_type": "regular"}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect("home")


class AdvertiserSignupView(SignupView):
    form_class = AdvertiserSignupForm
    extra_context = {"heading": "Create an advertiser account", "account_type": "advertiser"}
