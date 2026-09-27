from django.contrib import admin

from .models import AdvertiserProfile


@admin.register(AdvertiserProfile)
class AdvertiserProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website", "created_at")
    search_fields = ("company_name", "user__username", "user__email")
    raw_id_fields = ("user",)
