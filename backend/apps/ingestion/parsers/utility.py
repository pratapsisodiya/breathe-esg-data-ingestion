"""
Utility electricity CSV parser (Green Button / portal export format).

Research basis:
───────────────
Facilities teams typically retrieve electricity data from their utility's online
portal using "Download My Data" or the Green Button standard (a US DOE initiative
adopted by major utilities including PG&E, ComEd, National Grid).

Green Button exports come in two flavours:
- Green Button Connect My Data (CMD): machine-to-machine API feed
- Green Button Download My Data (DMD): manually exported CSV or XML

We handle the CSV export (DMD) because:
1. It's what a facilities coordinator actually does — log in, click export, email CSV.
2. The CMD API requires OAuth registration per utility, impossible for a prototype.
3. Similar portal CSVs (non-Green-Button) follow the same column structure.

Key realities of utility CSV exports we handle:
1. Billing periods ≠ calendar months. A utility may bill from the 14th of one
   month to the 13th of the next. This means "January electricity" actually covers
   Dec 14 – Jan 13. We store period_start/period_end exactly as they appear,
   not aligned to calendar months. Alignment is the PM's job downstream.

2. Mixed units: large commercial/industrial sites may export in MWh while
   smaller offices export in kWh. We normalise to kWh for emission factor lookup.

3. Anomaly detection: a >20% deviation in usage from the same meter in the
   previous billing period (same approximate duration) is flagged. This catches
   data entry errors, meter malfunctions, and unusual consumption spikes that
   analysts should verify before approving.

4. Multiple meters per tenant: one CSV may contain readings from many meters
   at many sites. Each row becomes one EmissionRecord.

What we don't handle:
- Interval data (15-minute / hourly readings) — these would need aggregation
- Natural gas on the same bill (some dual-fuel utility bills combine both)
- Demand charges (kW peak) — we store but don't use for emissions
"""

import csv
import logging
from decimal import Decimal
from datetime import datetime

from . import emission_factors as ef

logger = logging.getLogger(__name__)

# Flexible column name mapping — different utilities use different headers
COLUMN_MAP = {
    # Account/meter identifiers
    "Account_ID": "account_id",
    "AccountID": "account_id",
    "Account Number": "account_id",
    "Meter_ID": "meter_id",
    "MeterID": "meter_id",
    "Meter ID": "meter_id",
    "Meter Number": "meter_id",
    "Site_Name": "site_name",
    "Site Name": "site_name",
    "Location": "site_name",
    # Billing period
    "Billing_Start": "billing_start",
    "Start_Date": "billing_start",
    "Read Date Start": "billing_start",
    "From": "billing_start",
    "Billing_End": "billing_end",
    "End_Date": "billing_end",
    "Read Date End": "billing_end",
    "To": "billing_end",
    # Usage
    "Usage_kWh": "usage",
    "Usage": "usage",
    "Consumption": "usage",
    "Energy Usage": "usage",
    "kWh": "usage",
    "Usage_Unit": "usage_unit",
    "Unit": "usage_unit",
    "UOM": "usage_unit",
    # Other
    "Demand_kW": "demand_kw",
    "Peak Demand": "demand_kw",
    "Total_Cost_USD": "cost",
    "Amount": "cost",
    "Tariff_Code": "tariff",
    "Rate Code": "tariff",
}

# Anomaly detection threshold (fraction)
ANOMALY_THRESHOLD = 0.20  # 20% deviation from same-meter previous period


def parse_date_flexible(value) -> "datetime.date":
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def normalise_to_kwh(usage: Decimal, unit: str) -> Decimal:
    """Normalise energy usage to kWh."""
    u = str(unit).strip().lower()
    if u in ("kwh", "kw·h", "kw-h", "kilowatt-hour", ""):
        return usage
    if u in ("mwh", "mw·h", "megawatt-hour"):
        return usage * 1000
    if u in ("gwh", "gigawatt-hour"):
        return usage * 1_000_000
    raise ValueError(f"Unrecognised energy unit: {unit!r}")


def parse(file_path: str, data_source_config: dict) -> dict:
    """
    Parse a utility portal CSV export.

    Args:
        file_path: Path to uploaded CSV file.
        data_source_config: DataSource.config dict. Expected structure:
            {
              "meter_lookup": {
                "MTR-001": {"country": "GB", "site": "HQ London"},
                "MTR-002": {"country": "IN", "site": "Factory Pune"}
              }
            }

    Returns:
        {"records": [...], "errors": [...]}
    """
    meter_lookup = data_source_config.get("meter_lookup", {})

    # Load file
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(file_path, encoding=enc) as f:
                reader = csv.DictReader(f)
                raw_rows = [{k.strip(): (v.strip() if v is not None else "") for k, v in row.items() if k is not None} for row in reader]
            break
        except Exception:
            continue
    else:
        raise ValueError("Could not read utility CSV file")

    # Map column names
    def remap(row):
        return {COLUMN_MAP.get(k, k): v for k, v in row.items()}
    rows_mapped = [remap(r) for r in raw_rows]

    if not rows_mapped:
        raise ValueError("File contains no data rows")

    col_sample = set(rows_mapped[0].keys())
    required = {"billing_start", "billing_end", "usage"}
    missing = required - col_sample
    if missing:
        raise ValueError(f"Required columns not found in utility CSV: {missing}")

    # Build a lookup of previous-period usage per meter for anomaly detection
    # {meter_id: [(billing_start, billing_end, kwh), ...]} sorted by date
    previous_usage: dict[str, list] = {}

    records = []
    errors = []

    for idx, row in enumerate(rows_mapped):
        row_num = idx + 2
        raw = row

        try:
            # Dates
            period_start = parse_date_flexible(row["billing_start"])
            period_end = parse_date_flexible(row["billing_end"])

            # IDs
            account_id = str(row.get("account_id", "")).strip()
            meter_id = str(row.get("meter_id", "")).strip()
            site_name = str(row.get("site_name", "")).strip()

            # Usage
            usage_raw = Decimal(str(row["usage"]).strip().replace(",", ""))
            usage_unit = str(row.get("usage_unit", "kWh")).strip() or "kWh"
            usage_kwh = normalise_to_kwh(usage_raw, usage_unit)

            # Location from meter_lookup or fallback
            meter_info = meter_lookup.get(meter_id, {})
            country = meter_info.get("country", "")
            site = meter_info.get("site", site_name or meter_id or account_id)
            location = site

            # Emission factor
            grid_factor = ef.GRID_FACTORS.get(country, ef.GRID_FACTORS["DEFAULT"])
            ef_used = f"{ef.FACTOR_SOURCE} – Grid electricity: {country or 'DEFAULT'} ({grid_factor} kg CO2e/kWh)"
            co2e_kg = float(usage_kwh) * grid_factor

            # Anomaly detection: compare to previous period for same meter
            needs_review = False
            needs_review_reason = ""
            meter_key = meter_id or account_id
            prev = previous_usage.get(meter_key, [])
            if prev:
                last_usage = prev[-1][2]
                if last_usage and last_usage > 0:
                    deviation = abs(float(usage_kwh) - float(last_usage)) / float(last_usage)
                    if deviation > ANOMALY_THRESHOLD:
                        needs_review = True
                        needs_review_reason = (
                            f"Usage {float(usage_kwh):.0f} kWh deviates {deviation:.0%} "
                            f"from previous period ({float(last_usage):.0f} kWh)"
                        )

            # Store for next iteration
            if meter_key not in previous_usage:
                previous_usage[meter_key] = []
            previous_usage[meter_key].append((period_start, period_end, usage_kwh))

            # Source row ID for deduplication
            source_row_id = f"UTIL-{account_id}-{meter_id}-{period_start}"

            records.append({
                "source_type": "UTILITY",
                "scope": "SCOPE_2",
                "category": f"Purchased electricity – {country or 'Grid'} ({ef_used.split('–')[1].strip()[:50]})",
                "activity_description": f"Electricity: {site}, Meter {meter_id}",
                "activity_quantity": float(usage_raw),
                "activity_unit": usage_unit,
                "quantity_normalized": float(usage_kwh),
                "unit_normalized": "kWh",
                "emission_factor_used": ef_used,
                "emission_factor_value": grid_factor,
                "co2e_kg": round(co2e_kg, 4),
                "period_start": period_start,
                "period_end": period_end,
                "location": location,
                "location_country": country,
                "raw_row": raw,
                "source_row_id": source_row_id,
                "needs_review": needs_review,
                "needs_review_reason": needs_review_reason,
            })

        except Exception as exc:
            logger.warning(f"Utility parser row {row_num}: {exc}")
            errors.append({"row": row_num, "error": str(exc), "raw": raw})

    return {"records": records, "errors": errors}
