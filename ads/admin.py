from django.contrib import admin

from .models import AdClick, AdImpression, AdUnit, AdvertiserProfile, Campaign


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website", "created_at")
    search_fields = ("company_name", "user__username", "user__email")
    raw_id_fields = ("user",)


class AdUnitInline(admin.StackedInline):
    model = AdUnit
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    inlines = [AdUnitInline]
    list_display = ("name", "advertiser", "status", "budget", "start_date", "end_date")
    list_filter = ("status",)
    list_select_related = ("advertiser",)
    search_fields = ("name", "advertiser__username")
    raw_id_fields = ("advertiser",)


@admin.register(AdUnit)
class AdUnitAdmin(admin.ModelAdmin):
    list_display = ("headline", "campaign", "target_url", "created_at")
    list_select_related = ("campaign",)
    search_fields = ("headline", "campaign__name")
    raw_id_fields = ("campaign",)


class ReadOnlyTelemetryAdmin(admin.ModelAdmin):
    """Telemetry is append-only: visible in the admin, never editable."""

    list_display = ("created_at", "ad_unit", "campaign", "user")
    list_filter = ("created_at",)
    list_select_related = ("ad_unit__campaign", "user")
    search_fields = ("ad_unit__headline", "ad_unit__campaign__name", "user__username")
    date_hierarchy = "created_at"

    @admin.display(description="Campaign", ordering="ad_unit__campaign__name")
    def campaign(self, obj):
        return obj.ad_unit.campaign

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdImpression)
class AdImpressionAdmin(ReadOnlyTelemetryAdmin):
    pass


@admin.register(AdClick)
class AdClickAdmin(ReadOnlyTelemetryAdmin):
    pass
