"""
SAP MB51 (Material Document List) flat file parser.

Research basis:
───────────────
SAP MB51 is the standard transaction for material document lists. When a
sustainability team asks the ERP team for "fuel consumption data", this is the
report they get — exported via List → Export → Spreadsheet.

Key realities of SAP MB51 exports we handle:
1. German column headers: SAP defaults to language-specific column names.
   Clients with German SAP instances (common in manufacturing) produce headers
   like "Buchungsdatum" not "Posting Date", "Menge" not "Quantity".

2. German decimal format: Quantities use period as thousand separator and comma
   as decimal separator: 1.234,56 = 1234.56 in Python. This is the locale-aware
   German number format (de_DE). Direct float() conversion silently gives wrong
   results (1.234,56 → ValueError, but "1.234" → 1.234 instead of 1234.0).

3. DD.MM.YYYY dates: SAP German dates are day-first, not ISO 8601. strptime
   with %d.%m.%Y handles this correctly.

4. Movement types drive Scope classification:
   - 201 (goods issue to cost center): fuel was consumed → Scope 1
   - 261 (goods issue for order): fuel consumed in production → Scope 1
   - 101 (goods receipt for PO): fuel or material purchased → Scope 3
   - 501 (goods receipt without PO): same → Scope 3
   Movement types outside these sets are logged and skipped.

5. Plant codes are meaningless without a lookup table. DE01 might mean
   Stuttgart, IN02 might mean Pune. The lookup lives in DataSource.config so
   it's configurable per client without code changes.

6. The material description (Materialkurztext) is how we identify fuel type.
   We do keyword matching because SAP material numbers (MATNR) are client-specific
   and can't be normalised across clients without a master data table.

What we don't handle (see DECISIONS.md):
- Goods movements for non-fuel procurement (Scope 3 Cat 1 of purchased goods)
- Multi-currency amounts (we ingest quantities, not financial values, for emissions)
- WBS elements, profit centers, or CO object assignments
"""

import re
import csv
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path

from . import emission_factors as ef

logger = logging.getLogger(__name__)

# SAP German column name → our internal key
GERMAN_COLUMN_MAP = {
    "Buchungsdatum": "posting_date",
    "Belegdatum": "document_date",
    "Belegnummer": "document_number",
    "Pos.": "line_item",
    "Positionsnummer": "line_item",
    "Werk": "plant",
    "Lagerort": "storage_location",
    "Bewegungsart": "movement_type",
    "Material": "material_number",
    "Materialkurztext": "material_description",
    "Menge": "quantity",
    "Basismengeneinheit": "unit",
    "Kostenstelle": "cost_center",
    # Also accept English variants (some SAP configs are in English)
    "Posting Date": "posting_date",
    "Document Date": "document_date",
    "Document Number": "document_number",
    "Plant": "plant",
    "Movement Type": "movement_type",
    "Material": "material_number",
    "Material Description": "material_description",
    "Quantity": "quantity",
    "Base Unit of Measure": "unit",
    "Cost Center": "cost_center",
}

# Movement types that represent consumption (Scope 1 direct emissions)
CONSUMPTION_MVTS = {"201", "261", "551", "971"}
# Movement types that represent procurement (Scope 3)
PROCUREMENT_MVTS = {"101", "501", "561", "901"}


def parse_german_decimal(value) -> Decimal:
    """
    Convert German decimal string to Python Decimal.

    German format: 1.234,56 (thousand sep = period, decimal sep = comma)
    English format: 1,234.56 (opposite)

    Strategy: strip periods (thousand separators), then replace comma with
    period for Python parsing.
    """
    if not value or str(value).strip() == "":
        raise ValueError("Empty quantity value")
    s = str(value).strip()
    # Handle both German and English decimal formats
    if "," in s and "." in s:
        # Ambiguous: determine by position of last separator
        last_comma = s.rfind(",")
        last_period = s.rfind(".")
        if last_comma > last_period:
            # German: 1.234,56 → 1234.56
            s = s.replace(".", "").replace(",", ".")
        else:
            # English: 1,234.56 → 1234.56
            s = s.replace(",", "")
    elif "," in s:
        # Only comma present → German decimal: 1234,56 → 1234.56
        s = s.replace(",", ".")
    # If only period or no separator, treat as standard decimal
    return Decimal(s)


def parse_date(value) -> "datetime.date":
    """Try DD.MM.YYYY (SAP German default) then YYYY-MM-DD then MM/DD/YYYY."""
    s = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def resolve_fuel_type(material_desc: str) -> str | None:
    """Return our fuel type key by matching the material description against known keywords."""
    desc_lower = material_desc.lower()
    for keyword, fuel_key in ef.MATERIAL_TO_FUEL.items():
        if keyword in desc_lower:
            return fuel_key
    return None


def normalise_unit(sap_unit: str, quantity: Decimal) -> tuple[Decimal, str]:
    """
    Convert SAP unit codes to a canonical unit and adjust quantity.

    Returns (normalised_quantity, canonical_unit_string).
    Canonical units: L (liquid fuels), KG (solid/gas by mass), M3 (gas by volume).
    """
    u = sap_unit.strip().upper()
    mapped = ef.SAP_UNIT_MAP.get(u)
    if mapped is None:
        raise ValueError(f"Unrecognised SAP unit: {sap_unit!r}")

    if u == "G":
        return quantity / 1000, "KG"
    if u == "T":
        return quantity * 1000, "KG"
    return quantity, mapped


def get_emission_factor(fuel_key: str, canonical_unit: str) -> tuple[float, str]:
    """
    Return (factor_value, factor_description) for a given fuel type and unit.
    Raises KeyError if no factor found.
    """
    if canonical_unit == "L":
        factor = ef.FUEL_FACTORS_PER_LITRE.get(fuel_key)
        if factor:
            return factor, f"{ef.FACTOR_SOURCE} – Fuel combustion: {fuel_key}, per litre"
    elif canonical_unit == "KG":
        factor = ef.FUEL_FACTORS_PER_KG.get(fuel_key)
        if factor:
            return factor, f"{ef.FACTOR_SOURCE} – Fuel combustion: {fuel_key}, per kg"
    elif canonical_unit == "M3":
        factor = ef.FUEL_FACTORS_PER_M3.get(fuel_key)
        if factor:
            return factor, f"{ef.FACTOR_SOURCE} – Fuel combustion: {fuel_key}, per m³"
    elif canonical_unit == "GAL":
        factor = ef.FUEL_FACTORS_PER_US_GALLON.get(fuel_key)
        if factor:
            return factor, f"{ef.FACTOR_SOURCE} – Fuel combustion: {fuel_key}, per US gallon"
    raise KeyError(f"No emission factor for {fuel_key!r} in unit {canonical_unit!r}")


def parse(file_path: str, data_source_config: dict) -> dict:
    """
    Parse an SAP MB51 flat-file export.

    Args:
        file_path: Path to the uploaded CSV or XLSX file.
        data_source_config: DataSource.config dict. Expected structure:
            {
              "plant_lookup": {
                "DE01": {"country": "DE", "site": "Stuttgart"},
                "IN02": {"country": "IN", "site": "Pune"}
              }
            }

    Returns:
        {
          "records": [list of dicts ready for EmissionRecord creation],
          "errors":  [{"row": int, "error": str, "raw": dict}]
        }
    """
    plant_lookup = data_source_config.get("plant_lookup", {})

    # ── Load file ─────────────────────────────────────────────────────────────
    if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
        # Try openpyxl if available, otherwise raise
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                raise ValueError("XLSX file is empty")
            headers = [str(c).strip() if c is not None else "" for c in rows[0]]
            raw_rows = [
                {headers[i]: (str(cell) if cell is not None else "") for i, cell in enumerate(row)}
                for row in rows[1:]
            ]
        except ImportError:
            raise ValueError("openpyxl required for XLSX parsing. Run: pip install openpyxl")
    else:
        # Try tab-separated first (SAP default), then comma
        for delimiter in ("\t", ",", ";"):
            try:
                with open(file_path, encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    raw_rows = [{k.strip(): (v.strip() if v is not None else "") for k, v in row.items() if k is not None} for row in reader]
                if len(raw_rows) > 0 and len(raw_rows[0]) >= 3:
                    break
            except Exception:
                continue
        else:
            with open(file_path, encoding="latin-1") as f:
                reader = csv.DictReader(f)
                raw_rows = [{k.strip(): (v.strip() if v is not None else "") for k, v in row.items() if k is not None} for row in reader]

    # ── Map German column names to internal keys ───────────────────────────────
    def remap(row):
        return {GERMAN_COLUMN_MAP.get(k, k): v for k, v in row.items()}
    rows_mapped = [remap(r) for r in raw_rows]

    if not rows_mapped:
        raise ValueError("File contains no data rows")

    col_sample = set(rows_mapped[0].keys())
    required = {"posting_date", "plant", "movement_type", "material_description", "quantity", "unit"}
    missing = required - col_sample
    if missing:
        raise ValueError(f"Required columns not found in SAP export: {missing}")

    records = []
    errors = []

    for idx, row in enumerate(rows_mapped):
        row_num = idx + 2  # 1-indexed, +1 for header
        raw = row

        try:
            # ── Movement type ──────────────────────────────────────────────────
            mvt = str(row.get("movement_type", "")).strip()
            if mvt in CONSUMPTION_MVTS:
                scope = "SCOPE_1"
                activity_verb = "Consumption"
            elif mvt in PROCUREMENT_MVTS:
                scope = "SCOPE_3"
                activity_verb = "Procurement"
            else:
                errors.append({
                    "row": row_num,
                    "error": f"Movement type {mvt!r} not in handled set — skipped",
                    "raw": raw,
                })
                continue

            # ── Dates ──────────────────────────────────────────────────────────
            posting_date = parse_date(row["posting_date"])

            # ── Quantity ───────────────────────────────────────────────────────
            qty_raw = parse_german_decimal(row["quantity"])
            sap_unit = str(row["unit"]).strip()
            qty_norm, unit_norm = normalise_unit(sap_unit, qty_raw)

            # ── Plant / location ───────────────────────────────────────────────
            plant_code = str(row.get("plant", "")).strip()
            plant_info = plant_lookup.get(plant_code, {})
            country = plant_info.get("country", "")
            site = plant_info.get("site", plant_code)
            location = f"Plant {plant_code} – {site}" if site else plant_code

            # ── Fuel type and emission factor ──────────────────────────────────
            material_desc = str(row.get("material_description", "")).strip()
            doc_num = str(row.get("document_number", "")).strip()
            line_item = str(row.get("line_item", "")).strip()

            needs_review = False
            needs_review_reason = ""
            co2e_kg = None
            ef_value = None
            ef_used = ""
            category = f"SAP {activity_verb} – {material_desc}"

            if scope == "SCOPE_1":
                fuel_key = resolve_fuel_type(material_desc)
                if fuel_key:
                    try:
                        ef_value, ef_used = get_emission_factor(fuel_key, unit_norm)
                        co2e_kg = float(qty_norm) * ef_value
                        category = f"Stationary combustion – {fuel_key.replace('_', ' ').title()}"
                    except KeyError as e:
                        needs_review = True
                        needs_review_reason = str(e)
                else:
                    needs_review = True
                    needs_review_reason = (
                        f"Could not identify fuel type from material description: {material_desc!r}"
                    )
                    category = f"Stationary combustion – Unidentified ({material_desc})"
            else:
                # Scope 3 procurement: no emission factor applied at ingestion
                # (would require spend-based approach or LCA data not available here)
                needs_review = True
                needs_review_reason = "Procurement row: emission factor requires manual assignment"
                category = f"Purchased goods – {material_desc}"

            source_row_id = f"SAP-{doc_num}-{line_item}" if doc_num else ""

            records.append({
                "source_type": "SAP_FUEL",
                "scope": scope,
                "category": category,
                "activity_description": f"{activity_verb}: {material_desc}, Plant {plant_code}",
                "activity_quantity": float(qty_raw),
                "activity_unit": sap_unit,
                "quantity_normalized": float(qty_norm),
                "unit_normalized": unit_norm,
                "emission_factor_used": ef_used,
                "emission_factor_value": ef_value,
                "co2e_kg": round(co2e_kg, 4) if co2e_kg is not None else None,
                "period_start": posting_date,
                "period_end": posting_date,
                "location": location,
                "location_country": country,
                "raw_row": raw,
                "source_row_id": source_row_id,
                "needs_review": needs_review,
                "needs_review_reason": needs_review_reason,
            })

        except Exception as exc:
            logger.warning(f"SAP parser row {row_num}: {exc}")
            errors.append({"row": row_num, "error": str(exc), "raw": raw})

    return {"records": records, "errors": errors}
