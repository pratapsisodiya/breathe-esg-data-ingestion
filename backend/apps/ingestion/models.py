from django.db import models
from django.contrib.auth.models import User

from apps.tenants.models import Tenant


class DataSource(models.Model):
    """
    A configured data source for a tenant.

    Stores metadata needed to correctly interpret each source's output.
    For example:
      - SAP_FUEL config holds a plant_lookup dict mapping plant codes (e.g. "DE01")
        to country codes and site names, since plant codes are client-specific and
        not interpretable without this lookup.
      - UTILITY config holds a meter_lookup mapping meter IDs to site info and
        the country/grid region used to select the right emission factor.
      - CONCUR config can hold a default_country for hotel emission factor fallback.

    This keeps parser logic generic while supporting per-client configuration.
    """

    class SourceType(models.TextChoices):
        SAP_FUEL = "SAP_FUEL", "SAP Fuel & Procurement"
        UTILITY = "UTILITY", "Utility Electricity"
        CONCUR = "CONCUR", "Corporate Travel (Concur)"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="data_sources")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    name = models.CharField(max_length=255)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.source_type}) — {self.tenant.name}"


class IngestionRun(models.Model):
    """
    One ingestion run = one file upload.

    Records the full lifecycle of a single ingestion: who triggered it, which
    file was uploaded, what happened to each row, and final statistics.

    error_log is a list of dicts: [{"row": 3, "error": "Missing Menge", "raw": {...}}]
    This lets analysts see exactly which rows failed and why without digging into logs.

    The raw_file field stores the uploaded file so we can re-parse if the parser
    is updated, or provide it for audit. In production this would point to S3.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name="runs"
    )
    triggered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="ingestion_runs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    raw_file = models.FileField(upload_to="ingestion_files/", null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)

    rows_total = models.IntegerField(default=0)
    rows_ok = models.IntegerField(default=0)
    rows_failed = models.IntegerField(default=0)
    rows_flagged = models.IntegerField(default=0)

    # Row-level parse errors: [{row: int, error: str, raw: dict}]
    error_log = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Run #{self.id} — {self.data_source.name} ({self.status})"
