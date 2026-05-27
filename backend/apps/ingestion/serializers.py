from rest_framework import serializers
from .models import DataSource, IngestionRun


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "name", "source_type", "created_at"]


class IngestionRunSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="data_source.name", read_only=True)
    source_type = serializers.CharField(source="data_source.source_type", read_only=True)
    triggered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IngestionRun
        fields = [
            "id", "source_name", "source_type", "triggered_by_name",
            "started_at", "completed_at", "status", "original_filename",
            "rows_total", "rows_ok", "rows_failed", "rows_flagged", "error_log",
        ]

    def get_triggered_by_name(self, obj):
        if obj.triggered_by:
            return obj.triggered_by.get_full_name() or obj.triggered_by.email
        return "System"
