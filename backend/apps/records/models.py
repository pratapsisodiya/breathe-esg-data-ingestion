from django.db import models
from django.contrib.auth.models import User

from apps.tenants.models import Tenant


class EmissionRecord(models.Model):
    """
    The canonical normalized record of a single emissions-relevant activity.

    Design rationale:
    ─────────────────
    One record per source row (not aggregated at ingestion time). This is a
    deliberate choice: aggregating at ingestion destroys the ability to trace
    a specific tonne of CO2e back to its originating document. Auditors
    need that chain. We aggregate in the API summary endpoint instead.

    raw_row stores the original parsed dict exactly as it came from the CSV,
    before any normalization or conversion. This is the audit anchor: if the
    emission factor changes next year, or a unit conversion was disputed, the
    original source data is always recoverable.

    source_row_id is a stable identifier from the source system (e.g., SAP
    document number + line, Concur entry ID). Used to detect duplicate uploads:
    if the same row appears in two different ingestion runs, we can flag it
    rather than silently double-counting.

    co2e_kg is computed at ingestion time and stored. We do not compute it on
    the fly because emission factor databases (DEFRA, EPA) publish new versions
    annually. A record approved with DEFRA 2023 factors must stay that way even
    after DEFRA 2024 is loaded. Stored + versioned is the only correct approach.

    Scope classification:
    ─────────────────────
    SCOPE_1: Direct emissions from sources the company owns or controls.
             In our SAP data: fuel combustion (movement type 201, fuel materials).
    SCOPE_2: Purchased electricity, heat, steam, or cooling.
             All utility electricity records.
    SCOPE_3: All other indirect emissions. In our data:
             - SAP procurement goods receipts (movement type 101, Scope 3 Cat 1)
             - All Concur travel (Scope 3 Cat 6: Business Travel)

    Unit normalization:
    ───────────────────
    activity_quantity / activity_unit = raw values from source (may be L, GAL,
    MWh, kWh, M3, KG). quantity_normalized / unit_normalized = values in a
    canonical unit before applying the emission factor. For fuels we normalize
    to litres (L) before lookup; for electricity to kWh; for distance to km.
    We keep both because the raw unit is needed for the audit trail.
    """

    class SourceType(models.TextChoices):
        SAP_FUEL = "SAP_FUEL", "SAP Fuel & Procurement"
        UTILITY = "UTILITY", "Utility Electricity"
        CONCUR = "CONCUR", "Corporate Travel (Concur)"

    class Scope(models.TextChoices):
        SCOPE_1 = "SCOPE_1", "Scope 1 – Direct Emissions"
        SCOPE_2 = "SCOPE_2", "Scope 2 – Purchased Energy"
        SCOPE_3 = "SCOPE_3", "Scope 3 – Value Chain"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        APPROVED = "APPROVED", "Approved"
        FLAGGED = "FLAGGED", "Flagged – Needs Attention"
        REJECTED = "REJECTED", "Rejected"

    # ── Ownership ────────────────────────────────────────────────────────────
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="emission_records"
    )
    ingestion_run = models.ForeignKey(
        "ingestion.IngestionRun",
        on_delete=models.SET_NULL,
        null=True,
        related_name="records",
    )

    # ── Source classification ─────────────────────────────────────────────────
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    # GHG Protocol-aligned category string, e.g.:
    #   "Stationary combustion – Diesel EN590"
    #   "Purchased electricity – eGRID SERC"
    #   "Business travel – Air, Economy, Long-haul"
    category = models.CharField(max_length=200)

    # ── Activity data (raw, as received from source) ──────────────────────────
    activity_description = models.CharField(max_length=500)
    activity_quantity = models.DecimalField(max_digits=16, decimal_places=4)
    # Raw unit string exactly from source: "L", "KG", "M3", "GAL", "kWh", "MWh"
    activity_unit = models.CharField(max_length=30)

    # ── Normalized activity data ──────────────────────────────────────────────
    # Always in a canonical unit suitable for emission factor lookup.
    # Fuels → L (litres). Electricity → kWh. Distance → km.
    quantity_normalized = models.DecimalField(max_digits=16, decimal_places=4)
    unit_normalized = models.CharField(max_length=20)

    # ── Emissions calculation ─────────────────────────────────────────────────
    # Which emission factor database and version was used, e.g.:
    #   "DEFRA 2023 – Fuel: Diesel"
    #   "eGRID 2022 – SERC region"
    #   "DEFRA 2023 – Business travel: flights, economy, long-haul"
    emission_factor_used = models.CharField(max_length=200, blank=True)
    # The numeric factor value (kg CO2e per unit_normalized)
    emission_factor_value = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    # Total CO2e in kilograms. NULL if emission factor could not be resolved
    # (e.g., unrecognised material, missing IATA code). These rows are
    # automatically flagged for analyst attention.
    co2e_kg = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)

    # ── Temporal and spatial context ──────────────────────────────────────────
    # period_start/end reflect the billing or activity period from the source,
    # NOT the ingestion date. Utility billing periods don't align to calendar
    # months (e.g., 14th–13th). We preserve that reality here and let the API
    # handle period-alignment questions in aggregation queries.
    period_start = models.DateField()
    period_end = models.DateField()
    # Human-readable location, e.g. "Plant DE01 – Stuttgart" or "HQ London"
    location = models.CharField(max_length=255, blank=True)
    # ISO 3166-1 alpha-2, used for grid emission factor and hotel factor selection
    location_country = models.CharField(max_length=2, blank=True)

    # ── Source traceability ───────────────────────────────────────────────────
    # The complete original parsed row. Never edited after creation.
    raw_row = models.JSONField()
    # Stable source-side identifier for deduplication across re-uploads.
    # SAP: concatenation of document number + line (MBLNR + ZEILE)
    # Concur: Report_ID + Entry_ID
    # Utility: Account_ID + Meter_ID + billing_start
    source_row_id = models.CharField(max_length=200, blank=True)

    # ── Review workflow ───────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_records",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # is_locked = True after the record is approved AND the period has been
    # exported for audit. Locked records cannot be edited, re-reviewed, or deleted.
    is_locked = models.BooleanField(default=False)

    # Parser-set anomaly flags (set automatically, not by analysts)
    needs_review = models.BooleanField(default=False)
    needs_review_reason = models.CharField(max_length=500, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "scope"]),
            models.Index(fields=["tenant", "period_start", "period_end"]),
            models.Index(fields=["source_type", "source_row_id"]),
        ]

    def __str__(self):
        return (
            f"{self.source_type} | {self.scope} | {self.category} "
            f"| {self.period_start} | {self.co2e_kg} kg CO2e"
        )

    @property
    def co2e_tonnes(self):
        if self.co2e_kg is None:
            return None
        return round(float(self.co2e_kg) / 1000, 4)
