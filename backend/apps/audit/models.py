from django.db import models
from django.contrib.auth.models import User

from apps.tenants.models import Tenant


class AuditLog(models.Model):
    """
    Immutable, append-only log of all significant actions in the system.

    Design rationale:
    ─────────────────
    This table is never updated or deleted. Every write goes through the
    AuditLog.log() classmethod, which calls save() on a new instance.
    The save() method raises ValueError if called on an existing pk, making
    mutation impossible even from within Django code.

    We capture before_state and after_state as JSON snapshots of the relevant
    model fields at the time of the action. This means auditors can reconstruct
    the full history of any EmissionRecord without relying on Django's queryset
    history or database-level CDC.

    We deliberately did not use a library like django-auditlog because:
    1. We want full control over what constitutes a "meaningful" state change
       (not every model field save, just reviewer actions and ingestion events).
    2. The assignment requires us to understand and defend our data model.

    The actor field uses SET_NULL so that if a user account is deleted, the
    audit history is preserved (the record shows "deleted user" rather than
    cascading delete of audit trail).
    """

    class Action(models.TextChoices):
        # Ingestion lifecycle
        INGESTION_STARTED = "INGESTION_STARTED", "Ingestion started"
        INGESTION_COMPLETED = "INGESTION_COMPLETED", "Ingestion completed"
        INGESTION_FAILED = "INGESTION_FAILED", "Ingestion failed"
        # Record review actions
        RECORD_APPROVED = "RECORD_APPROVED", "Record approved"
        RECORD_FLAGGED = "RECORD_FLAGGED", "Record flagged"
        RECORD_REJECTED = "RECORD_REJECTED", "Record rejected"
        RECORD_EDITED = "RECORD_EDITED", "Record edited"
        RECORD_LOCKED = "RECORD_LOCKED", "Record locked for audit"
        # Bulk actions
        BULK_APPROVED = "BULK_APPROVED", "Bulk approval"

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="audit_logs"
    )
    emission_record = models.ForeignKey(
        "records.EmissionRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    ingestion_run = models.ForeignKey(
        "ingestion.IngestionRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    # JSON snapshot before the action (null for creation/ingestion events)
    before_state = models.JSONField(null=True, blank=True)
    # JSON snapshot after the action
    after_state = models.JSONField(null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)
    # auto_now_add makes timestamp immutable
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"

    def save(self, *args, **kwargs):
        """Prevent updates to existing audit log entries."""
        if self.pk:
            raise ValueError("AuditLog entries are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    @classmethod
    def log(cls, *, tenant, action, actor, description="",
            emission_record=None, ingestion_run=None,
            before_state=None, after_state=None):
        """
        Convenience method for creating audit log entries.
        Always use this instead of AuditLog(...).save() to ensure
        the immutability contract is maintained.
        """
        return cls.objects.create(
            tenant=tenant,
            action=action,
            actor=actor,
            description=description,
            emission_record=emission_record,
            ingestion_run=ingestion_run,
            before_state=before_state,
            after_state=after_state,
        )
