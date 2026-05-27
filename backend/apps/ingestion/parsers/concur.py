"""
Concur Standard Accounting Extract (SAE) CSV parser for corporate travel.

Research basis:
───────────────
SAP Concur is the dominant corporate travel and expense platform. When
sustainability teams ask for travel data, they typically receive a subset of
the Standard Accounting Extract (SAE) — an export format Concur generates for
finance integration. We chose the SAE CSV over the Concur API because:

1. The API requires OAuth 2.0 with company-admin credentials, which a prototype
   cannot provision without a real client relationship.
2. Finance teams already export SAE files for GL posting. Sustainability teams
   piggyback on that existing workflow.
3. The Navan (formerly TripActions) platform exports a similar CSV structure,
   so this parser handles both with minor column name mapping.

Key realities of Concur SAE exports for emissions:
1. Expense type is the primary classification mechanism. Concur uses configurable
   expense types; we handle the most common ones (Airfare, Hotel, Car Rental,
   Train, Taxi/Rideshare). Unrecognised types are logged.

2. Flight distance is never in the SAE. We get origin/destination IATA codes and
   must calculate distance ourselves. We use the Haversine formula on our IATA
   coordinate lookup table. Missing IATA codes flag the row for analyst review.

3. Cabin class affects the emission factor significantly: business class has ~3x
   the per-km footprint of economy (wider seat = larger share of aircraft weight
   and fuel burn allocated per passenger).

4. Hotel data gives us city/country and number of nights. We use a regional
   emission factor (kg CO2e per room-night) rather than property-specific data
   because the SAE doesn't identify the specific hotel brand or certification.

5. Ground transport: Concur sometimes populates a distance field, sometimes not.
   When distance is absent, we flag for review. When present, we apply the
   mode-specific emission factor.

6. All travel = Scope 3, Category 6 (Business Travel) per GHG Protocol.

Radiative Forcing Index (RFI):
   Flights at altitude produce non-CO2 warming effects (contrails, NOx, cirrus
   cloud formation). DEFRA 2023 recommends including RFI by using factors that
   already incorporate a 1.9x RFI multiplier. Our FLIGHT_FACTORS already include
   this; we don't apply a separate multiplier.
"""

import csv
import math
import logging
from decimal import Decimal
from datetime import datetime, date

from . import emission_factors as ef

logger = logging.getLogger(__name__)

# Column name mapping: Concur field names → our internal keys
COLUMN_MAP = {
    # Report/entry identifiers
    "Report_ID": "report_id",
    "ReportID": "report_id",
    "Report ID": "report_id",
    "Entry_ID": "entry_id",
    "EntryID": "entry_id",
    "Entry ID": "entry_id",
    # Employee
    "Employee_ID": "employee_id",
    "EmployeeID": "employee_id",
    "Employee ID": "employee_id",
    "Employee_Name": "employee_name",
    "Employee Name": "employee_name",
    # Classification
    "Expense_Type": "expense_type",
    "Expense Type": "expense_type",
    "ExpenseType": "expense_type",
    "Category": "expense_type",
    # Date and amount
    "Transaction_Date": "transaction_date",
    "Transaction Date": "transaction_date",
    "TransactionDate": "transaction_date",
    "Date": "transaction_date",
    "Amount_USD": "amount_usd",
    "Amount": "amount_usd",
    "TransactionAmount": "amount_usd",
    # Merchant
    "Merchant_Name": "merchant",
    "Merchant Name": "merchant",
    "Vendor": "merchant",
    # Flight-specific
    "Origin_IATA": "origin_iata",
    "Origin": "origin_iata",
    "From_Airport": "origin_iata",
    "Dest_IATA": "dest_iata",
    "Destination": "dest_iata",
    "To_Airport": "dest_iata",
    "Cabin_Class": "cabin_class",
    "Class": "cabin_class",
    "Service Class": "cabin_class",
    # Hotel-specific
    "Hotel_City": "hotel_city",
    "Hotel City": "hotel_city",
    "City": "hotel_city",
    "Hotel_Country": "hotel_country",
    "Hotel Country": "hotel_country",
    "Country": "hotel_country",
    "Hotel_Nights": "hotel_nights",
    "Hotel Nights": "hotel_nights",
    "Nights": "hotel_nights",
    "Number of Nights": "hotel_nights",
    # Ground transport
    "Distance_KM": "distance_km",
    "Distance": "distance_km",
    "Miles": "distance_miles",
    "Description": "description",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points using the Haversine formula.
    Returns distance in kilometres.

    This gives the shortest path along the Earth's surface — a reasonable proxy
    for flight distance. Actual flight paths are longer due to routing and ATC,
    but for emission factor purposes the IATA-to-IATA great-circle distance is
    the accepted method (DEFRA 2023 guidance).
    """
    R = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_flight_distance(origin: str, dest: str) -> tuple[float, bool]:
    """
    Return (distance_km, was_estimated) for a flight leg.
    was_estimated = True if airport not found (uses fallback of 5000 km).
    """
    o = origin.strip().upper()
    d = dest.strip().upper()
    o_coords = ef.AIRPORT_COORDS.get(o)
    d_coords = ef.AIRPORT_COORDS.get(d)

    if o_coords and d_coords:
        return haversine_km(*o_coords, *d_coords), False
    return None, True


def classify_haul(distance_km: float) -> str:
    return "short_haul" if distance_km < ef.SHORT_HAUL_KM_THRESHOLD else "long_haul"


def parse_date(value) -> date:
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def parse(file_path: str, data_source_config: dict) -> dict:
    """
    Parse a Concur SAE CSV export.

    Args:
        file_path: Path to uploaded CSV file.
        data_source_config: DataSource.config dict. Expected structure:
            {
              "default_country": "IN"   // fallback for hotel country lookup
            }

    Returns:
        {"records": [...], "errors": [...]}
    """
    default_country = data_source_config.get("default_country", "")

    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(file_path, encoding=enc) as f:
                reader = csv.DictReader(f)
                raw_rows = [{k.strip(): (v.strip() if v is not None else "") for k, v in row.items() if k is not None} for row in reader]
            break
        except Exception:
            continue
    else:
        raise ValueError("Could not read Concur CSV file")

    def remap(row):
        return {COLUMN_MAP.get(k, k): v for k, v in row.items()}
    rows_mapped = [remap(r) for r in raw_rows]

    if not rows_mapped:
        raise ValueError("File contains no data rows")

    col_sample = set(rows_mapped[0].keys())
    if "expense_type" not in col_sample:
        raise ValueError("Required column 'Expense_Type' not found in Concur export")
    if "transaction_date" not in col_sample:
        raise ValueError("Required column 'Transaction_Date' not found in Concur export")

    records = []
    errors = []

    for idx, row in enumerate(rows_mapped):
        row_num = idx + 2
        raw = row

        try:
            expense_type = str(row.get("expense_type", "")).strip().lower()
            txn_date = parse_date(row["transaction_date"])
            report_id = str(row.get("report_id", "")).strip()
            entry_id = str(row.get("entry_id", "")).strip()
            source_row_id = f"CNC-{report_id}-{entry_id}" if report_id else ""
            description = str(row.get("description", "")).strip()
            merchant = str(row.get("merchant", "")).strip()

            # ── AIRFARE ────────────────────────────────────────────────────────
            if expense_type in ("airfare", "air", "airline", "flights", "flight"):
                origin = str(row.get("origin_iata", "")).strip().upper()
                dest = str(row.get("dest_iata", "")).strip().upper()
                cabin_raw = str(row.get("cabin_class", "economy")).strip().lower()
                cabin = ef.CABIN_CLASS_MAP.get(cabin_raw, "economy")

                if not origin or not dest:
                    records.append(_make_needs_review(
                        row_num, raw, source_row_id, txn_date,
                        "Airfare row missing IATA codes — cannot calculate distance",
                        "CONCUR", "SCOPE_3",
                        f"Business travel – Air ({cabin_raw}, {origin or '?'}→{dest or '?'})",
                    ))
                    continue

                distance_km, was_estimated = get_flight_distance(origin, dest)

                if distance_km is None:
                    records.append(_make_needs_review(
                        row_num, raw, source_row_id, txn_date,
                        f"Airport code(s) {origin}/{dest} not in lookup table — cannot compute distance",
                        "CONCUR", "SCOPE_3",
                        f"Business travel – Air ({cabin_raw}, {origin}→{dest})",
                    ))
                    continue

                haul = classify_haul(distance_km)
                factor = ef.FLIGHT_FACTORS[cabin][haul]
                co2e_kg = distance_km * factor
                ef_used = (
                    f"{ef.FACTOR_SOURCE} – Business travel: flights, "
                    f"{cabin}, {haul.replace('_', '-')}, incl. RFI"
                )

                needs_review = was_estimated
                reason = f"Distance estimated from lookup; airport {origin} or {dest} not in table" if was_estimated else ""

                records.append({
                    "source_type": "CONCUR",
                    "scope": "SCOPE_3",
                    "category": f"Business travel – Air, {cabin.title()}, {haul.replace('_', '-').title()}",
                    "activity_description": (
                        f"Flight {origin}→{dest}, {cabin.title()} class, "
                        f"{merchant or 'Airline'}"
                    ),
                    "activity_quantity": round(distance_km, 1),
                    "activity_unit": "km",
                    "quantity_normalized": round(distance_km, 1),
                    "unit_normalized": "km",
                    "emission_factor_used": ef_used,
                    "emission_factor_value": factor,
                    "co2e_kg": round(co2e_kg, 4),
                    "period_start": txn_date,
                    "period_end": txn_date,
                    "location": f"{origin}→{dest}",
                    "location_country": "",
                    "raw_row": raw,
                    "source_row_id": source_row_id,
                    "needs_review": needs_review,
                    "needs_review_reason": reason,
                })

            # ── HOTEL ──────────────────────────────────────────────────────────
            elif expense_type in ("hotel", "lodging", "accommodation", "hotel/lodging"):
                nights_raw = row.get("hotel_nights", "")
                try:
                    nights = int(float(str(nights_raw).strip()))
                except (ValueError, TypeError):
                    nights = 1  # assume 1 night if not specified

                hotel_country = str(row.get("hotel_country", default_country)).strip().upper()
                hotel_city = str(row.get("hotel_city", "")).strip()
                if not hotel_country and default_country:
                    hotel_country = default_country.upper()

                factor = ef.HOTEL_FACTORS.get(hotel_country, ef.HOTEL_FACTORS["DEFAULT"])
                co2e_kg = nights * factor
                ef_used = f"{ef.FACTOR_SOURCE} – Business travel: hotel, {hotel_country or 'DEFAULT'} ({factor} kg CO2e/room-night)"

                records.append({
                    "source_type": "CONCUR",
                    "scope": "SCOPE_3",
                    "category": f"Business travel – Hotel, {hotel_country or 'Unknown country'}",
                    "activity_description": (
                        f"Hotel: {hotel_city or 'Unknown city'}, {hotel_country}, "
                        f"{nights} night(s), {merchant or ''}"
                    ),
                    "activity_quantity": float(nights),
                    "activity_unit": "room-nights",
                    "quantity_normalized": float(nights),
                    "unit_normalized": "room-nights",
                    "emission_factor_used": ef_used,
                    "emission_factor_value": factor,
                    "co2e_kg": round(co2e_kg, 4),
                    "period_start": txn_date,
                    "period_end": txn_date,
                    "location": f"{hotel_city}, {hotel_country}",
                    "location_country": hotel_country,
                    "raw_row": raw,
                    "source_row_id": source_row_id,
                    "needs_review": not bool(hotel_country),
                    "needs_review_reason": "Hotel country unknown — emission factor may be incorrect" if not hotel_country else "",
                })

            # ── GROUND TRANSPORT ───────────────────────────────────────────────
            elif expense_type in ef.EXPENSE_TO_GROUND or "car" in expense_type or \
                    "taxi" in expense_type or "train" in expense_type or \
                    "bus" in expense_type or "ground" in expense_type or \
                    "rail" in expense_type or "rideshare" in expense_type or \
                    "uber" in expense_type:

                ground_key = ef.EXPENSE_TO_GROUND.get(expense_type, "taxi")
                factor = ef.GROUND_FACTORS.get(ground_key, ef.GROUND_FACTORS["DEFAULT"])

                distance_raw = row.get("distance_km", "") or row.get("distance_miles", "")
                distance_km = None

                if distance_raw and str(distance_raw).strip() not in ("", "nan"):
                    try:
                        d = float(str(distance_raw).strip())
                        if "distance_miles" in row and "distance_km" not in row:
                            d = d * 1.60934  # convert miles to km
                        distance_km = d
                    except ValueError:
                        pass

                if distance_km is None:
                    records.append(_make_needs_review(
                        row_num, raw, source_row_id, txn_date,
                        f"Ground transport row missing distance — cannot calculate emissions",
                        "CONCUR", "SCOPE_3",
                        f"Business travel – Ground transport ({expense_type})",
                    ))
                    continue

                co2e_kg = distance_km * factor
                ef_used = f"{ef.FACTOR_SOURCE} – Business travel: ground transport, {ground_key}"

                records.append({
                    "source_type": "CONCUR",
                    "scope": "SCOPE_3",
                    "category": f"Business travel – Ground transport, {ground_key.replace('_', ' ').title()}",
                    "activity_description": f"{expense_type.title()}: {merchant or description or 'Ground transport'}",
                    "activity_quantity": round(distance_km, 2),
                    "activity_unit": "km",
                    "quantity_normalized": round(distance_km, 2),
                    "unit_normalized": "km",
                    "emission_factor_used": ef_used,
                    "emission_factor_value": factor,
                    "co2e_kg": round(co2e_kg, 4),
                    "period_start": txn_date,
                    "period_end": txn_date,
                    "location": "",
                    "location_country": "",
                    "raw_row": raw,
                    "source_row_id": source_row_id,
                    "needs_review": False,
                    "needs_review_reason": "",
                })

            else:
                errors.append({
                    "row": row_num,
                    "error": f"Unrecognised expense type: {expense_type!r} — skipped",
                    "raw": raw,
                })

        except Exception as exc:
            logger.warning(f"Concur parser row {row_num}: {exc}")
            errors.append({"row": row_num, "error": str(exc), "raw": raw})

    return {"records": records, "errors": errors}


def _make_needs_review(row_num, raw, source_row_id, txn_date, reason,
                       source_type, scope, category):
    """Helper to create a flagged record when critical data is missing."""
    return {
        "source_type": source_type,
        "scope": scope,
        "category": category,
        "activity_description": f"Row {row_num}: {reason}",
        "activity_quantity": 0,
        "activity_unit": "",
        "quantity_normalized": 0,
        "unit_normalized": "",
        "emission_factor_used": "",
        "emission_factor_value": None,
        "co2e_kg": None,
        "period_start": txn_date,
        "period_end": txn_date,
        "location": "",
        "location_country": "",
        "raw_row": raw,
        "source_row_id": source_row_id,
        "needs_review": True,
        "needs_review_reason": reason,
    }
