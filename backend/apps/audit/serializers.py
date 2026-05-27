from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    record_id = serializers.IntegerField(source="emission_record_id", read_only=True)
    run_id = serializers.IntegerField(source="ingestion_run_id", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "actor_name", "record_id", "run_id",
            "description", "before_state", "after_state", "timestamp",
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.email
        return "Deleted user"
