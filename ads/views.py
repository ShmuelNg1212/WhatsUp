from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView, UpdateView

from .forms import CampaignForm
from .mixins import AdvertiserRequiredMixin, OwnedCampaignMixin, campaigns_owned_by
from .models import Campaign


class DashboardView(AdvertiserRequiredMixin, TemplateView):
    """The advertiser's home: company details and their campaigns."""

    template_name = "ads/dashboard.html"

    def get_context_data(self, **kwargs):
        campaigns = list(
            campaigns_owned_by(self.request.user).annotate(ad_count=Count("ad_units"))
        )
        return super().get_context_data(
            profile=getattr(self.request.user, "advertiser_profile", None),
            campaigns=campaigns,
            live_count=sum(c.is_live for c in campaigns),
            total_budget=sum((c.budget for c in campaigns), 0),
            **kwargs,
        )


class CampaignFormMixin(SuccessMessageMixin):
    form_class = CampaignForm
    template_name = "ads/campaign_form.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "advertiser": self.request.user}


class CampaignCreateView(AdvertiserRequiredMixin, CampaignFormMixin, CreateView):
    model = Campaign
    success_message = "Campaign “%(name)s” created. Now add an ad unit."

    def form_valid(self, form):
        form.instance.advertiser = self.request.user
        return super().form_valid(form)


class CampaignDetailView(OwnedCampaignMixin, DetailView):
    template_name = "ads/campaign_detail.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(ad_units=list(self.object.ad_units.all()), **kwargs)


class CampaignUpdateView(OwnedCampaignMixin, CampaignFormMixin, UpdateView):
    success_message = "Campaign “%(name)s” updated."


class CampaignDeleteView(OwnedCampaignMixin, SuccessMessageMixin, DeleteView):
    template_name = "ads/campaign_confirm_delete.html"
    success_url = reverse_lazy("ads:dashboard")

    def get_context_data(self, **kwargs):
        return super().get_context_data(ad_count=self.object.ad_units.count(), **kwargs)

    def get_success_message(self, cleaned_data):
        return f"Campaign “{self.object.name}” deleted."
