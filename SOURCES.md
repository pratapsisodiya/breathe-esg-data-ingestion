# SOURCES.md — Data Source Research and Sample Data Rationale

## Source 1: SAP MB51 (Fuel & Procurement)

### What we researched

SAP MB51 is the Material Document List transaction — the standard report for reviewing goods movements in SAP Materials Management (MM). We researched:

- **SAP transaction structure**: MB51 runs in the SAP GUI against the MSEG (material document segment) and MKPF (material document header) tables. Movement types (Bewegungsart) classify every goods movement: 101 (goods receipt), 201 (goods issue to cost center), 261 (goods issue for production order), etc.
- **Export format**: SAP supports List → Export → Spreadsheet, producing an XLSX file. Tab-separated flat files are also common when scripted via ABAP. The column names reflect the SAP data dictionary language: German headers in German-language systems, English in English systems.
- **Real German locale issues**: Quantities are formatted with German locale (1.234,56 = one thousand two hundred thirty-four point fifty-six). Dates are DD.MM.YYYY. These are not edge cases — they are the default for any German SAP installation.
- **Movement type significance for emissions**: 201 (goods issue to cost center) is fuel consumption — this is Scope 1. 101 (goods receipt) is procurement of goods/fuel from a supplier — this is Scope 3 Category 1.
- **Plant codes**: SAP plant codes are 4-character alphanumeric identifiers that are entirely client-specific. "DE01" means nothing without knowing the client's plant configuration. A lookup table in `DataSource.config` maps these to countries and site names.

### What our sample data looks like and why

Our `sap_mb51_export.csv` (37 rows) contains:
- **German column headers** (`Buchungsdatum`, `Werk`, `Menge`, `Basismengeneinheit`): because the client has a German-language SAP instance — standard for a German manufacturing company
- **DD.MM.YYYY dates**: SAP German default
- **Three plants**: DE01 (Stuttgart, Germany), IN02 (Pune, India), US03 (Detroit, USA) — realistic for a multinational manufacturer
- **Multiple fuels**: Diesel EN590 (European standard diesel), Erdgas (German natural gas), Ultra Low Sulfur Diesel (US standard) — each plant uses locally-appropriate fuel grades
- **Multiple movement types**: 201 (consumption), 261 (production order issue), 101 (procurement receipts)
- **US plant uses GAL units**: SAP installations in the US often use US gallons for fuel, not litres — our parser handles both
- **One row with empty Menge** (Row 25/SYNTH-0099): triggers a parse error — realistic because SAP sometimes exports incomplete rows when the posting is still open or the material movement was reversed
- **One unrecognised material** (SYNTH-0099, "Synthetic Lubricant Base Oil"): triggers `needs_review` because we can't determine fuel type from the description — realistic because not everything in the SAP material list is a fuel

### What would break in production

1. **Column names beyond our map**: If the client exports SAP with a custom layout that includes fields not in our `GERMAN_COLUMN_MAP`, we'd miss them. Solution: make the column map configurable per DataSource.
2. **Character encoding**: SAP sometimes exports UTF-16 with BOM, or Latin-1. We try `utf-8-sig` and `latin-1`; other encodings would need explicit handling.
3. **Multi-currency**: Some SAP exports include amounts in multiple currencies. We ignore financial amounts (we only need quantities) but currency fields can cause type errors in pandas.
4. **Reversed postings**: SAP uses negative quantities for goods movement reversals (movement type 102 reverses 101). We'd need to handle these or they'd appear as negative emission records.
5. **IDoc format**: Some companies configure SAP to push IDocs to middleware rather than allow manual exports. IDocs are XML-like and require a completely different parser.

---

## Source 2: Utility Portal CSV (Electricity)

### What we researched

- **Green Button standard**: A US DOE initiative that standardizes electricity usage data downloads from utility portals. Adopted by major utilities: PG&E, ComEd, National Grid US, Eversource, Con Edison, and ~60 others. Green Button Download My Data (DMD) produces a CSV or XML file that facilities teams download manually from the utility's website.
- **Non-Green-Button portals**: European utilities (EnBW in Germany, MSEDCL in India) don't follow the Green Button standard but produce structurally similar CSVs with account ID, meter ID, billing period, and usage. Column names differ (some use `Verbrauch_kWh`, `Datum_Von`, etc.) but the structure is the same.
- **Billing period alignment**: Utilities bill monthly, but the billing cycle start date is determined by when the meter was installed and when the utility reads it — not by calendar month. A meter installed on the 14th will bill on a 14th-to-13th cycle indefinitely. This is a real operational fact that affects how you aggregate utility data.
- **kWh vs MWh**: Residential and small commercial meters report in kWh. Large industrial and commercial sites (factories, data centers) report in MWh because their usage is in the hundreds of MWh per month.
- **eGRID / IEA grid factors**: US emission factors vary significantly by grid region (eGRID). Europe uses national average factors. India's factor (0.708 kg CO2e/kWh) is higher than Germany's (0.366 kg CO2e/kWh) due to coal dominance.

### What our sample data looks like and why

Our `utility_portal_export.csv` (24 rows) contains:
- **Stuttgart HQ (MTR-001, Germany, DE grid, kWh)**: Bills on 14th-13th cycle — realistic non-calendar alignment. Usage peaks in Nov-Jan (heating season in Germany's cold climate). **November 2024 shows a 49% spike** (68,400 kWh vs 45,800 previous period) — will be automatically flagged by the anomaly detector. In reality this could be a heating system failure or a cold snap, or a data entry error — exactly what an analyst needs to investigate.
- **Pune Factory (MTR-002, India, IN grid, MWh)**: Bills on calendar months (1st-31st). High usage May-Aug (summer cooling load). Reports in MWh because it's a factory-scale site. The parser converts MWh → kWh for emission factor application.
- **Different tariff codes**: ENBW-GD-S (EnBW commercial standard) and MSEDCL-HT-II (Maharashtra State Electricity Distribution Company, High Tension category) — these are real Indian utility rate codes for industrial customers.

### What would break in production

1. **PDF bills**: If the utility only provides PDF invoices (common for smaller facilities), the CSV parser won't work. Requires OCR pipeline (see TRADEOFFS.md).
2. **Interval data**: Smart meters produce 15-minute or hourly data instead of monthly summaries. Our parser expects monthly rows; interval data would produce thousands of rows per meter per month requiring aggregation.
3. **Multi-fuel utility bills**: Some utilities include natural gas and electricity on the same bill. Our parser handles electricity only; gas would need to be extracted separately.
4. **MSEDCL portal sessions**: Indian utility portals (MSEDCL, BESCOM) often have session timeouts and CAPTCHAs that make automated download difficult. Manual download remains the realistic path.
5. **Missing meter IDs**: Some portal exports don't include meter IDs, only account IDs. Without meter IDs, we can't distinguish between multiple meters on the same account.

---

## Source 3: Concur SAE (Corporate Travel)

### What we researched

- **SAP Concur Standard Accounting Extract (SAE)**: The primary file format for Concur expense data integration. Finance teams export it daily or weekly for GL posting. It's highly configurable (up to 400 columns in version 3.x) but finance teams typically export a subset. We handle the common subset.
- **Expense type taxonomy**: Concur uses configurable expense types. The most common for travel: Airfare, Hotel, Car Rental, Train, Taxi/Rideshare, Meals. Each maps to a different emissions calculation method.
- **Flight emissions methodology**: DEFRA 2023 uses passenger-km as the activity metric. Distance is calculated from IATA airport codes using great-circle distance. Radiative Forcing Index (1.9x) is included in DEFRA's published factors for business travel.
- **Cabin class multipliers**: Business class emits ~3x more per km than economy because the wider seat takes up more of the aircraft's weight and volume allocation. DEFRA 2023 publishes separate factors for economy, premium economy, business, and first.
- **Hotel emission factors**: Cornell Hotel Sustainability Benchmarking (HSB) Index 2023 + DEFRA 2023 provide regional room-night factors (kg CO2e per room-night). These vary significantly: India (10.0) vs UK (6.0) vs France (4.0) due to grid intensity differences.
- **Navan (TripActions)**: Produces a similar CSV export with slightly different column names. Our column map handles both.

### What our sample data looks like and why

Our `concur_expense_extract.csv` (40 rows) contains:
- **Multiple employees**: EMP-042 (Rahul Mehta, Mumbai-based), EMP-017 (Ananya Singh, Delhi-based), EMP-031 (Marcus Weber, Frankfurt-based), EMP-055 (Priya Krishnan, Bangalore-based) — realistic for a multinational with Indian and European headcount
- **Realistic flight routes**: BOM→FRA (Mumbai to Frankfurt, 7,015 km — long haul), DEL→LHR (Delhi to London, 6,716 km — long haul), BLR→BOM (Bangalore to Mumbai, 844 km — short haul), MUC→LHR (Munich to London, 1,453 km — short haul). These are real routes Indian companies fly frequently.
- **Mixed cabin classes**: Most economy, some business (senior executive travel, BOM→DXB, DEL→LHR, DEL→SIN). Business class rows produce 3x the emissions of equivalent economy routes.
- **Hotel nights across countries**: UK (6.0 kg/night), DE (5.5 kg/night), IN (10.0 kg/night), SG (7.5 kg/night), US (8.0 kg/night) — uses real regional factors
- **Ground transport with distances**: Train (Deutsche Bahn Stuttgart→Berlin: 580 km realistic, Berlin ICE distance), car rental (1,240 km Stuttgart-Munich-Zurich-Stuttgart route, realistic for a 3-city road trip)
- **One row with missing distance** (ENT-040, taxi without distance): triggers `needs_review` — realistic because Concur often doesn't capture ground transport distances for local taxi rides
- **Return flights included**: Every outbound has a corresponding return flight — realistic, employees come back

### What would break in production

1. **IATA codes not in our lookup table**: We cover 50+ airports. A flight to a smaller regional airport (e.g., Ahmedabad AMD, Jaipur JAI) would trigger `needs_review` if not in our table. Solution: expand the table or integrate with an IATA coordinate API.
2. **Itemized hotel bills**: Concur allows itemizing hotel expenses into room rate, taxes, parking, meals. Each itemization creates a separate row. Our parser would count each row as a separate stay. Need to aggregate by Report_ID + Entry_ID.
3. **Multi-currency amounts**: Our sample uses USD. In practice, employees submit in their local currency (INR, EUR, GBP). The Amount field in Concur is the reimbursement currency, not the transaction currency. This doesn't affect our emissions calculation (we don't use amounts) but is something analysts might want for spend reporting.
4. **Rail vs. flight misclassification**: Some employees book rail tickets through the Concur "Airfare" expense type. The IATA codes would be blank or invalid. We'd flag it as `needs_review` due to missing IATA codes, but it could be falsely categorised.
5. **Ferries, helicopters, private jets**: Our ground transport category doesn't cover these. They'd be logged as parse errors.
