from rest_framework import serializers
from .models import EmissionRecord


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Compact serializer for list views."""
    co2e_tonnes = serializers.ReadOnlyField()
    reviewed_by_name = serializers.SerializerMethodField()
    run_id = serializers.IntegerField(source="ingestion_run_id", read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            "id", "source_type", "scope", "category", "activity_description",
            "activity_quantity", "activity_unit", "co2e_kg", "co2e_tonnes",
            "period_start", "period_end", "location", "status",
            "needs_review", "needs_review_reason", "is_locked",
            "reviewed_by_name", "reviewed_at", "run_id", "created_at",
            "review_note",
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None


class EmissionRecordSerializer(EmissionRecordListSerializer):
    """Full serializer including raw_row for detail views."""

    class Meta(EmissionRecordListSerializer.Meta):
        fields = EmissionRecordListSerializer.Meta.fields + [
            "quantity_normalized", "unit_normalized",
            "emission_factor_used", "emission_factor_value",
            "location_country", "review_note", "raw_row", "source_row_id",
        ]
