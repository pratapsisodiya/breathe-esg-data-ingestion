# MODEL.md — Data Model

## Overview

The data model is built around three core concerns:
1. **Source fidelity**: every normalized record traces back to its exact origin row
2. **Audit correctness**: every change is permanently recorded with before/after state
3. **Multi-tenant isolation**: one client can never see another client's data

---

## Entity Relationship

```
Tenant
  └── UserProfile (extends Django User)
  └── DataSource (SAP_FUEL | UTILITY | CONCUR)
       └── IngestionRun (one per file upload)
            └── EmissionRecord[] (one per source row)
                    └── AuditLog[] (one per action on that record)
```

---

## Multi-Tenancy

**Approach**: Row-level isolation via `tenant` FK on every model.

Every model has a `tenant` FK. Every API view filters its queryset by `request.user.profile.tenant`. This means one tenant can never retrieve another's data through the API.

**Why not PostgreSQL schemas or separate databases?**
Row-level isolation is the simplest approach that works correctly for a prototype with a small number of tenants. The tradeoff: it requires discipline in every view to include the tenant filter — a missed filter exposes data. A production system would add PostgreSQL Row-Level Security (RLS) as a defence-in-depth measure, making a missed filter safe at the database level. That's noted in TRADEOFFS.md.

**UserProfile** extends Django's built-in `User` via `OneToOneField` rather than swapping `AUTH_USER_MODEL`. This keeps Django admin compatibility and avoids the complexity of a custom user model for a prototype.

---

## EmissionRecord — The Core Model

This is the canonical normalized record of a single emissions-relevant activity.

### Design decisions

**One record per source row, not aggregated.**
We preserve row-level granularity rather than aggregating at ingestion time (e.g., monthly totals). Reason: auditors need to trace every tonne of CO2e back to a specific document in the source system. Aggregation destroys that chain. We aggregate in the API summary endpoint instead.

**`raw_row` (JSONField) stores the original parsed dict.**
This is the audit anchor. If the emission factor changes, if the unit conversion is disputed, or if the column mapping was wrong, the original source data is always recoverable. The source never needs to be re-exported.

**`co2e_kg` is stored, not computed on the fly.**
Emission factor databases (DEFRA, EPA) publish new versions annually. A record approved with DEFRA 2023 factors must remain at that value even after DEFRA 2024 is loaded. Storing the computed value alongside `emission_factor_used` (a string describing the source and version) is the only approach that preserves calculation provenance.

**`source_row_id` enables idempotent re-ingestion.**
If a client re-exports the same SAP period twice (common — they often export overlapping date ranges), we can detect duplicate rows by matching `source_row_id`. Currently we log them; a production system would deduplicate automatically.

**`needs_review` / `needs_review_reason` are set by parsers, not analysts.**
When a parser encounters an anomaly (unrecognised unit, missing IATA code, >20% usage spike), it sets `needs_review = True` and records the reason. This surfaces automatically in the analyst UI without manual triage. The analyst then decides whether to approve, flag, or reject.

### Fields

| Field | Type | Purpose |
|---|---|---|
| `tenant` | FK → Tenant | Row-level isolation |
| `ingestion_run` | FK → IngestionRun | Traceability to upload event |
| `source_type` | enum | SAP_FUEL, UTILITY, CONCUR |
| `scope` | enum | SCOPE_1, SCOPE_2, SCOPE_3 |
| `category` | CharField | GHG Protocol-aligned category string |
| `activity_description` | CharField | Human-readable description |
| `activity_quantity` | Decimal | Raw quantity from source |
| `activity_unit` | CharField | Raw unit from source (e.g. "L", "MWh") |
| `quantity_normalized` | Decimal | Quantity in canonical unit |
| `unit_normalized` | CharField | Canonical unit (L, kWh, km) |
| `emission_factor_used` | CharField | Factor source + version string |
| `emission_factor_value` | Decimal | Numeric factor (kg CO2e/unit) |
| `co2e_kg` | Decimal | Computed tCO2e × 1000, stored |
| `period_start` / `period_end` | Date | Activity period from source |
| `location` | CharField | Human-readable site |
| `location_country` | CharField | ISO 3166-1 alpha-2 for factor lookup |
| `raw_row` | JSON | Original parsed row (immutable) |
| `source_row_id` | CharField | Stable ID for deduplication |
| `status` | enum | PENDING, APPROVED, FLAGGED, REJECTED |
| `review_note` | TextField | Analyst annotation |
| `reviewed_by` / `reviewed_at` | FK / DateTime | Who approved and when |
| `is_locked` | Boolean | Prevents edit after audit export |
| `needs_review` | Boolean | Parser-set anomaly flag |
| `needs_review_reason` | CharField | Parser's reason for flagging |

---

## Scope Classification

We follow the GHG Protocol Corporate Standard:

| Source | Scope | GHG Protocol Category |
|---|---|---|
| SAP movement type 201/261 (fuel consumption) | Scope 1 | Stationary combustion |
| SAP movement type 101/501 (procurement) | Scope 3 | Cat 1: Purchased goods & services |
| Utility electricity | Scope 2 | Purchased electricity (location-based) |
| Concur airfare | Scope 3 | Cat 6: Business travel |
| Concur hotel | Scope 3 | Cat 6: Business travel |
| Concur ground transport | Scope 3 | Cat 6: Business travel |

**Why location-based Scope 2?**
Market-based Scope 2 (using supplier-specific emission factors or RECs) requires data we don't have at ingestion time. Location-based is the appropriate fallback per GHG Protocol guidance and requires only the country/grid region.

---

## DataSource — Per-Client Configuration

Each `DataSource` has a `config` JSONField that stores the metadata needed to correctly interpret that source's output without hardcoding it.

**SAP config example:**
```json
{
  "plant_lookup": {
    "DE01": {"country": "DE", "site": "Stuttgart Plant"},
    "IN02": {"country": "IN", "site": "Pune Factory"}
  }
}
```
SAP plant codes (e.g. "DE01") are client-specific 4-character codes. Without this lookup, we cannot determine the country (needed for Scope 2 grid factor selection) or a human-readable site name.

**Utility config example:**
```json
{
  "meter_lookup": {
    "MTR-001": {"country": "DE", "site": "Stuttgart HQ"},
    "MTR-002": {"country": "IN", "site": "Pune Factory"}
  }
}
```

**Concur config example:**
```json
{"default_country": "DE"}
```
Used as a fallback when hotel country is not specified in the export.

---

## IngestionRun — Ingestion Provenance

One `IngestionRun` per file upload. Records:
- Who triggered it (`triggered_by` FK to User)
- Which file (`raw_file`, `original_filename`)
- What happened (`rows_total`, `rows_ok`, `rows_failed`, `rows_flagged`)
- Row-level errors (`error_log` JSONField: list of `{row, error, raw}` dicts)
- The original file (stored in `media/ingestion_files/`)

The `raw_file` field means we can always re-parse with an updated parser if we fix a bug, or provide the original file to auditors.

---

## AuditLog — Immutable Append-Only Trail

`AuditLog` records are never updated or deleted. The `save()` method raises `ValueError` if called on an existing pk. All writes go through `AuditLog.log()` classmethod.

**What we log:**
- `INGESTION_STARTED` / `INGESTION_COMPLETED` / `INGESTION_FAILED` (lifecycle events)
- `RECORD_APPROVED` / `RECORD_FLAGGED` / `RECORD_REJECTED` / `RECORD_EDITED` (reviewer actions)
- `BULK_APPROVED` (bulk actions)

**`before_state` / `after_state`** capture the relevant mutable fields of the `EmissionRecord` at the time of the action: `status`, `review_note`, `activity_quantity`, `activity_unit`, `co2e_kg`. This allows auditors to see exactly what changed and when.

**Why not django-auditlog?**
We want full control over what constitutes a meaningful state change. django-auditlog logs every field save; we only want reviewer actions and ingestion events. We also want the immutability contract enforced at the Python level, not just at the DB level.

---

## Unit Normalization Strategy

| Raw unit | Canonical unit | Conversion |
|---|---|---|
| L (litres) | L | 1:1 |
| GAL (US gallon) | L | × 3.785 |
| G (grams) | KG | ÷ 1000 |
| T (metric tonnes) | KG | × 1000 |
| M3 (cubic metres) | M3 | 1:1 |
| kWh | kWh | 1:1 |
| MWh | kWh | × 1000 |
| km | km | 1:1 |
| miles | km | × 1.60934 |
| room-nights | room-nights | 1:1 |

We normalize before applying emission factors so the factor lookup is unambiguous. The raw unit is always preserved in `activity_unit` for the audit trail.
