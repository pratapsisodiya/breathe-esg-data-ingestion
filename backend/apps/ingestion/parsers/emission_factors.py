"""
Emission factor tables used at ingestion time.

Source: UK DEFRA/DESNZ Greenhouse Gas Conversion Factors 2023
(https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting)

These are stored as module-level constants rather than database rows because:
1. They change annually (we need to know which version was used per record)
2. The version is captured in EmissionRecord.emission_factor_used as a string
3. A proper production system would version these in the DB and allow updates

All values are kg CO2e per unit (not just CO2 — includes CH4 and N2O warming).
"""

FACTOR_SOURCE = "DEFRA 2023"

# ── Fuel combustion factors (Scope 1) ─────────────────────────────────────────
# Key: (fuel_type_key, unit) → kg CO2e per unit
# SAP units: L (litres), KG (kilograms), M3 (cubic metres), GAL (US gallons)

FUEL_FACTORS_PER_LITRE = {
    # kg CO2e per litre
    "diesel": 2.68,
    "petrol": 2.31,
    "gasoline": 2.31,  # US term for petrol
    "hvo": 0.195,       # Hydrotreated Vegetable Oil (biofuel)
}

FUEL_FACTORS_PER_KG = {
    # kg CO2e per kg
    "natural_gas": 2.204,
    "lpg": 1.555,
    "coal": 2.393,
    "fuel_oil": 3.179,
}

FUEL_FACTORS_PER_M3 = {
    # kg CO2e per cubic metre (at standard temperature and pressure)
    "natural_gas": 1.921,
}

FUEL_FACTORS_PER_US_GALLON = {
    # kg CO2e per US gallon (converted from per-litre: 1 US gal = 3.785 L)
    "diesel": 2.68 * 3.785,   # 10.14
    "petrol": 2.31 * 3.785,   # 8.74
    "gasoline": 2.31 * 3.785,
}

# Map SAP material description keywords to fuel type keys (lowercase matching)
MATERIAL_TO_FUEL = {
    "diesel": "diesel",
    "en590": "diesel",         # European diesel grade EN590
    "heizöl": "diesel",        # German: heating oil
    "heizoel": "diesel",
    "gasoil": "diesel",
    "petrol": "petrol",
    "benzin": "petrol",        # German: petrol
    "gasoline": "gasoline",
    "natural gas": "natural_gas",
    "erdgas": "natural_gas",   # German: natural gas
    "naturgas": "natural_gas",
    "lpg": "lpg",
    "flüssiggas": "lpg",       # German: LPG
    "flüssiggas": "lpg",
    "kohle": "coal",           # German: coal
    "coal": "coal",
    "hvo": "hvo",
    "fuel oil": "fuel_oil",
}

# Map SAP unit codes to canonical unit strings
SAP_UNIT_MAP = {
    "L": "L",
    "LT": "L",     # alternate SAP code for litres
    "KG": "KG",
    "G": "KG",     # grams — will be divided by 1000
    "T": "KG",     # metric tonnes — will be multiplied by 1000
    "M3": "M3",
    "GAL": "GAL",  # US gallon
    "GL": "GAL",   # SAP code for US gallon in some configs
}

# ── Grid electricity factors (Scope 2) ────────────────────────────────────────
# Key: ISO 3166-1 alpha-2 country code → kg CO2e per kWh
# Sources: IEA 2022 Emission Factors, DEFRA 2023

GRID_FACTORS = {
    "GB": 0.207,   # UK National Grid 2023
    "DE": 0.366,   # Germany 2023 (still coal-heavy)
    "IN": 0.708,   # India 2023 (coal-dominated)
    "US": 0.386,   # US average 2023 (EPA eGRID national)
    "FR": 0.051,   # France (nuclear-heavy)
    "NO": 0.020,   # Norway (hydro-dominated)
    "AU": 0.610,   # Australia 2023
    "CN": 0.581,   # China 2023
    "SG": 0.408,   # Singapore 2023
    "DEFAULT": 0.500,  # global average fallback
}

# ── Flight emission factors (Scope 3, Category 6) ─────────────────────────────
# kg CO2e per passenger-km
# Includes radiative forcing index (RFI = 1.9x) per DEFRA 2023 guidance.
# RFI accounts for non-CO2 warming effects (contrails, NOx) at altitude.
# Short-haul threshold: < 3,700 km (typical of intra-European flights)

FLIGHT_FACTORS = {
    "economy": {
        "short_haul": 0.255,   # kg CO2e per pax-km
        "long_haul": 0.195,
    },
    "premium_economy": {
        "short_haul": 0.349,
        "long_haul": 0.299,
    },
    "business": {
        "short_haul": 0.510,
        "long_haul": 0.585,    # wider seat = larger share of aircraft footprint
    },
    "first": {
        "short_haul": 0.765,
        "long_haul": 0.780,
    },
}

SHORT_HAUL_KM_THRESHOLD = 3700

# Map Concur cabin class strings to our factor keys
CABIN_CLASS_MAP = {
    "economy": "economy",
    "economy class": "economy",
    "coach": "economy",
    "premium economy": "premium_economy",
    "premium": "premium_economy",
    "business": "business",
    "business class": "business",
    "first": "first",
    "first class": "first",
}

# ── Hotel emission factors (Scope 3, Category 6) ──────────────────────────────
# kg CO2e per room-night
# Source: Cornell Hotel Sustainability Benchmarking Index 2023 + DEFRA 2023

HOTEL_FACTORS = {
    "GB": 6.0,
    "US": 8.0,
    "DE": 5.5,
    "IN": 10.0,    # high grid intensity + less efficient HVAC
    "FR": 4.0,
    "AU": 9.5,
    "CN": 14.0,
    "SG": 7.5,
    "DEFAULT": 8.0,
}

# ── Ground transport factors (Scope 3, Category 6) ────────────────────────────
# kg CO2e per passenger-km
# Source: DEFRA 2023

GROUND_FACTORS = {
    "car_rental": 0.170,
    "taxi": 0.150,
    "rideshare": 0.150,
    "uber": 0.150,
    "train": 0.041,
    "rail": 0.041,
    "bus": 0.089,
    "coach": 0.027,
    "DEFAULT": 0.150,  # fallback to taxi-like vehicle
}

# Map Concur expense type strings to ground transport keys
EXPENSE_TO_GROUND = {
    "car rental": "car_rental",
    "rental car": "car_rental",
    "auto rental": "car_rental",
    "taxi": "taxi",
    "taxi/rideshare": "rideshare",
    "rideshare": "rideshare",
    "uber": "uber",
    "lyft": "rideshare",
    "train": "train",
    "rail": "train",
    "amtrak": "train",
    "eurostar": "train",
    "bus": "bus",
    "coach": "coach",
    "ground transport": "taxi",  # generic fallback
}

# ── IATA airport coordinates ───────────────────────────────────────────────────
# (latitude, longitude) for great-circle distance calculation.
# Covers the airports most likely to appear in corporate travel from
# India-headquartered companies with European and US operations.

AIRPORT_COORDS = {
    # India
    "BOM": (19.0896, 72.8656),   # Mumbai Chhatrapati Shivaji
    "DEL": (28.5665, 77.1031),   # Delhi Indira Gandhi
    "BLR": (13.1986, 77.7066),   # Bangalore Kempegowda
    "HYD": (17.2403, 78.4294),   # Hyderabad Rajiv Gandhi
    "MAA": (12.9941, 80.1709),   # Chennai Anna International
    "CCU": (22.6520, 88.4463),   # Kolkata Netaji Subhas
    "PNQ": (18.5822, 73.9197),   # Pune
    "AMD": (23.0772, 72.6347),   # Ahmedabad
    # UK & Europe
    "LHR": (51.4700, -0.4543),   # London Heathrow
    "LGW": (51.1537, -0.1821),   # London Gatwick
    "FRA": (50.0379, 8.5622),    # Frankfurt Main
    "CDG": (49.0097, 2.5478),    # Paris Charles de Gaulle
    "AMS": (52.3105, 4.7683),    # Amsterdam Schiphol
    "MUC": (48.3538, 11.7861),   # Munich
    "DUS": (51.2895, 6.7668),    # Düsseldorf
    "BER": (52.3667, 13.5033),   # Berlin Brandenburg
    "ZRH": (47.4647, 8.5492),    # Zurich
    "MAD": (40.4719, -3.5626),   # Madrid Barajas
    "BCN": (41.2974, 2.0833),    # Barcelona El Prat
    "FCO": (41.8003, 12.2389),   # Rome Fiumicino
    "MXP": (45.6306, 8.7281),    # Milan Malpensa
    # US & Canada
    "JFK": (40.6413, -73.7781),  # New York JFK
    "EWR": (40.6895, -74.1745),  # Newark
    "LGA": (40.7769, -73.8740),  # LaGuardia
    "SFO": (37.6213, -122.3790), # San Francisco
    "LAX": (33.9425, -118.4081), # Los Angeles
    "ORD": (41.9742, -87.9073),  # Chicago O'Hare
    "BOS": (42.3656, -71.0096),  # Boston Logan
    "DFW": (32.8998, -97.0403),  # Dallas/Fort Worth
    "SEA": (47.4502, -122.3088), # Seattle-Tacoma
    "ATL": (33.6407, -84.4277),  # Atlanta Hartsfield-Jackson
    "MIA": (25.7959, -80.2870),  # Miami
    "YYZ": (43.6777, -79.6248),  # Toronto Pearson
    # Middle East & Asia Pacific
    "DXB": (25.2532, 55.3657),   # Dubai International
    "DOH": (25.2609, 51.6138),   # Doha Hamad
    "AUH": (24.4330, 54.6511),   # Abu Dhabi
    "SIN": (1.3644, 103.9915),   # Singapore Changi
    "HKG": (22.3080, 113.9185),  # Hong Kong
    "NRT": (35.7720, 140.3929),  # Tokyo Narita
    "ICN": (37.4602, 126.4407),  # Seoul Incheon
    "PEK": (40.0799, 116.6031),  # Beijing Capital
    "PVG": (31.1443, 121.8083),  # Shanghai Pudong
    "BKK": (13.6811, 100.7472),  # Bangkok Suvarnabhumi
    "KUL": (2.7456, 101.7099),   # Kuala Lumpur
    "SYD": (-33.9461, 151.1772), # Sydney Kingsford Smith
    "MEL": (-37.6690, 144.8410), # Melbourne Tullamarine
}
