from django.contrib import admin

from .models import AdvertiserProfile, Campaign


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website", "created_at")
    search_fields = ("company_name", "user__username", "user__email")
    raw_id_fields = ("user",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "advertiser", "status", "budget", "start_date", "end_date")
    list_filter = ("status",)
    list_select_related = ("advertiser",)
    search_fields = ("name", "advertiser__username")
    raw_id_fields = ("advertiser",)
