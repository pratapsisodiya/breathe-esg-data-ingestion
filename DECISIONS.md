# DECISIONS.md — Ambiguity Resolution Log

Every significant decision made during the build, with reasoning and what I'd ask the PM.

---

## SAP Export Format

**Decision**: Handle SAP MB51 flat-file CSV export (List → Export → Spreadsheet in SAP GUI), not OData or BAPI.

**Reasoning**: OData requires SAP BASIS to activate the service, configure OAuth or basic auth, and whitelist the client's IP. BAPI calls require RFC connectivity, SAP credentials, and the `pyrfc` library (C dependencies, non-trivial to deploy). A sustainability analyst does not have access to any of this. What they have is: the ability to email the ERP team, who run MB51, export to XLSX, and send the file. That's the realistic ingestion path for 90% of mid-market companies.

**What I'd ask the PM**: "Does the client have SAP S/4HANA Cloud or on-prem? S/4HANA Cloud has a managed OData API (SAP Analytics Cloud integration) that might be accessible without BASIS involvement. If they're on-prem and on a legacy version, the flat file is the only realistic option for a prototype."

---

## SAP: German Column Headers

**Decision**: Map German column headers to English internal keys, not require English headers.

**Reasoning**: SAP defaults to the language of the system installation. German SAP instances (extremely common in German manufacturing clients) produce German column names: "Buchungsdatum", "Menge", "Basismengeneinheit". Requiring the client to change their SAP language config just to export ESG data is not acceptable. The parser accepts both German and English headers via a COLUMN_MAP dictionary.

**What I'd ask the PM**: "What language is the client's SAP system configured in? If it's Japanese or French, we'd need to extend the column map."

---

## SAP: German Decimal Format

**Decision**: Parse German decimal format (1.234,56 → 1234.56) with disambiguation logic.

**Reasoning**: German locale uses period as a thousand separator and comma as a decimal separator, opposite of English. Python's float() and pandas default parsing both fail silently or raise errors on this format. We detect the format by examining the positions of the last comma and period in the string — if the last comma is to the right of the last period, it's German format.

**What I'd ask the PM**: Nothing — this is a non-negotiable reality of SAP German exports.

---

## SAP: Scope Classification by Movement Type

**Decision**: Classify SAP records by movement type. 201/261 (goods issue) = Scope 1 consumption. 101/501 (goods receipt) = Scope 3 procurement.

**Reasoning**: Movement type is the only reliable programmatic indicator of whether fuel was consumed vs. purchased. Material description keywords are unreliable for scope classification. A goods receipt (101) for diesel doesn't mean combustion happened — it means diesel arrived at the warehouse. A goods issue (201) to a cost center means it was consumed in an operation.

**Tradeoff**: We don't apply emission factors to Scope 3 procurement rows (they'd require spend-based or LCA data not available in the SAP extract). These rows are flagged for analyst attention.

---

## Utility: Portal CSV over PDF or API

**Decision**: Handle utility portal CSV downloads (Green Button DMD format), not PDF bills or utility APIs.

**Reasoning**:
- **PDF**: Fragile, provider-specific, requires OCR or template-based extraction. Not worth the complexity for a 4-day prototype. Mentioned in TRADEOFFS.md.
- **Utility API**: No standard. PG&E, ComEd, and National Grid all have different APIs requiring separate OAuth registrations per client per utility. A facilities team at a company with 20 meters at 8 utilities would need 8 separate API integrations. Not feasible.
- **Portal CSV**: The Green Button Download My Data standard (DOE, adopted by major US utilities) produces a consistent CSV format. Even non-Green-Button utilities produce similar CSV exports from their portals. This is what a facilities manager actually does.

**What I'd ask the PM**: "How many different utility providers does the client use? If it's a single utility with a robust API, it might be worth the API integration effort. If it's 5+ utilities, the CSV approach is the only realistic one."

---

## Utility: Billing Periods Don't Align to Calendar Months

**Decision**: Store `period_start` / `period_end` exactly as they appear in the export, without aligning to calendar months.

**Reasoning**: A utility may bill from the 14th of one month to the 13th of the next. This means "January electricity" covers Dec 14 – Jan 13. Forcing alignment to calendar months would require us to:
1. Split a billing period across months (complex, introduces rounding)
2. Know the exact daily consumption pattern (unavailable)
3. Make assumptions that could introduce reporting errors

The correct approach is to preserve the actual billing period and let the reporting layer (out of scope for this prototype) handle period alignment. Auditors see the actual billing period, which is what appears on the invoice.

**What I'd ask the PM**: "Does your reporting framework (CSRD, GHG Protocol) require calendar-month alignment, or can it accept billing-period data? Some frameworks accept billing period data directly."

---

## Utility: Anomaly Detection Threshold

**Decision**: Flag records where usage deviates >20% from the previous period for the same meter.

**Reasoning**: A 20% deviation is a meaningful signal — it could indicate a meter fault, data entry error, or a genuine operational change (equipment upgrade, temporary shutdown). Below 20%, seasonal variation and billing period length differences explain most variation. Above 20%, analyst attention is warranted before the data goes to auditors.

**Caveat**: The comparison is sequential (period N vs. period N-1), not year-over-year. Year-over-year would be more meaningful for detecting seasonal patterns but requires 13 months of history. For a new deployment, we may only have a few months.

**What I'd ask the PM**: "Should we flag based on year-over-year comparison instead? That would require at least 12 months of historical data before anomalies can be detected."

---

## Travel: Concur SAE CSV over API

**Decision**: Handle Concur Standard Accounting Extract (SAE) CSV, not Concur's REST API.

**Reasoning**: Concur's API requires OAuth 2.0 with company-admin credentials provisioned by the client's Concur administrator. This takes weeks to set up and requires a partnership agreement. Finance teams already export SAE files for their ERP (SAP, Oracle, etc.) posting workflow. Sustainability teams can receive the same file. The SAE CSV is a known, documented format.

**Note**: Navan (formerly TripActions) produces a nearly identical CSV structure, so our parser handles both with minor column name variation.

**What I'd ask the PM**: "Does the client use Concur or Navan? And does their finance team already export SAE files? If so, we can piggyback on an existing export rather than setting up a new one."

---

## Travel: Flight Distance Calculation

**Decision**: Calculate great-circle distance from IATA airport codes using the Haversine formula on a hardcoded coordinate lookup table, rather than a third-party API.

**Reasoning**:
- Third-party APIs (Google Maps, OAG, IATA) require API keys, have usage limits, and add cost.
- The Haversine formula on IATA coordinates gives accuracy within ~1-2% of actual flight paths for most routes. DEFRA's own guidance uses great-circle distance for business travel emissions.
- Actual flight paths are longer than great-circle (due to routing, ATC, jet streams), but the GHG Protocol and DEFRA 2023 explicitly endorse great-circle distance for this calculation.

**Our IATA lookup table** covers 50+ airports representing the most common routes for India-headquartered companies with European and US operations. Unknown airports trigger a `needs_review` flag.

**What I'd ask the PM**: "Should we integrate with an IATA coordinate API for coverage of all 10,000+ IATA airports? Or is the current coverage sufficient for this client's travel patterns?"

---

## Travel: Radiative Forcing Index

**Decision**: Use DEFRA 2023 flight emission factors that already include a 1.9x Radiative Forcing Index (RFI) multiplier.

**Reasoning**: Flights at altitude produce non-CO2 warming effects: contrail formation, NOx chemistry, and cirrus cloud enhancement. These are collectively captured by RFI. DEFRA 2023 recommends including RFI in business travel reporting. Our factors are pre-multiplied; we don't apply a separate multiplier. Some clients may want to report CO2-only (without RFI) — that would require separate factors.

**What I'd ask the PM**: "Does the client's reporting framework require CO2-only or CO2e including RFI? TCFD and CSRD typically accept either if disclosed consistently."

---

## Travel: Scope 3 Category 6 for All Travel

**Decision**: All Concur records are Scope 3, Category 6 (Business Travel) per GHG Protocol.

**Reasoning**: The GHG Protocol Corporate Standard is clear: travel on assets not owned or controlled by the company (commercial airlines, hotels, rental cars) is Scope 3 Cat 6. This applies regardless of who pays for it. Company-owned vehicles would be Scope 1 — but those would appear in SAP, not Concur.

---

## Emission Factor Source: DEFRA 2023

**Decision**: Use UK DEFRA/DESNZ Greenhouse Gas Conversion Factors 2023 for all emission factors.

**Reasoning**: DEFRA publishes annual factors that cover fuels, electricity grids, and business travel with full methodology documentation. They're widely accepted by CSRD, TCFD, and GHG Protocol reporting frameworks. We store the source and version as a string on each `EmissionRecord` (`emission_factor_used`). A production system would allow multiple factor databases (EPA, IEA, etc.) and update them annually.

**Note**: Grid electricity factors are supplemented with IEA 2022 national averages for countries not in DEFRA's scope (India, China, etc.).

---

## Auth: Token Authentication over JWT

**Decision**: Use Django REST Framework's `TokenAuthentication` (database-stored tokens), not JWT.

**Reasoning**: JWT adds complexity (refresh token rotation, invalidation challenges) that isn't needed for a prototype. DRF TokenAuth is simpler, tokens are immediately revocable (just delete from DB), and it works out of the box with DRF. The tradeoff is that every request requires a database lookup to validate the token — acceptable at prototype scale.

**What I'd ask the PM**: "Are there plans to scale to multiple backend instances? If so, JWT becomes attractive because it's stateless and doesn't require DB lookups per request."

---

## Deployment: Render (backend + frontend)

**Decision**: Deploy both Django backend and React frontend to Render.com.

**Reasoning**: Render supports Django + managed PostgreSQL with GitHub-connected auto-deploy and zero Docker configuration. The static site hosting for Vite + React is also handled natively on Render, making the entire stack deployable from a single `render.yaml` config file in the repository root. This eliminates cross-provider CORS complexity and keeps credentials and deploy configuration in one place.

**Why not Railway or Fly?**: Railway requires a separate Dockerfile or Nixpacks config and its free tier was recently restricted. Fly.io requires Docker and `fly.toml` setup that adds meaningful complexity for a prototype. Render's `render.yaml` blueprint is the fastest path from repository to live URL with a managed PostgreSQL instance included.

**What I'd ask the PM**: "Should we use Render's paid plan to avoid cold-start delays on the free tier? The free tier spins down after 15 minutes of inactivity, which means the first API call after idle will have a ~30s delay — fine for a prototype review, not acceptable for a client demo."
