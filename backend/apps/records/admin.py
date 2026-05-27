from django.contrib import admin
from .models import EmissionRecord

@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ["id", "source_type", "scope", "category", "co2e_kg", "status", "period_start", "tenant"]
    list_filter = ["source_type", "scope", "status", "tenant", "needs_review"]
    search_fields = ["category", "activity_description", "location"]
    readonly_fields = ["raw_row", "created_at", "updated_at"]
