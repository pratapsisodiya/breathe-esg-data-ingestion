from django.contrib import admin
from .models import DataSource, IngestionRun

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "source_type", "tenant", "created_at"]
    list_filter = ["source_type", "tenant"]

@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ["id", "data_source", "status", "rows_ok", "rows_failed", "started_at"]
    list_filter = ["status", "data_source__source_type"]
    readonly_fields = ["error_log"]
