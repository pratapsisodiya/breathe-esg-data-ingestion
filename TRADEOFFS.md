# TRADEOFFS.md — Three Things Deliberately Not Built

## 1. PDF Utility Bill Parsing

**What it is**: Many facilities teams receive electricity bills as PDF invoices by email, not as portal CSV downloads. A PDF parser would extract the relevant fields (usage, billing period, account ID) from these PDFs automatically.

**Why we didn't build it**: PDF parsing is a fundamentally brittle problem. Utilities don't use a standard PDF layout — National Grid's PDF looks nothing like PG&E's, which looks nothing like MSEDCL's. Template-based parsers (using coordinate-based field extraction) break whenever the utility redesigns their invoice. ML-based document extraction (Google Document AI, AWS Textract) adds cost, latency, and a new service dependency. Either approach adds 2-3 days of work to handle even a handful of utility formats.

**What we built instead**: The Green Button portal CSV download, which is:
1. Machine-readable by design
2. Standardized across US utilities
3. What a well-run facilities team would use anyway (it's what their energy management software ingests)

**What would change in production**: If a client genuinely can only provide PDFs, we'd use AWS Textract with custom template training per utility. The normalized output would feed into the same `EmissionRecord` model — the ingestion pipeline handles it. The cost is implementation time and per-page OCR costs.

---

## 2. Real-Time API Ingestion from SAP OData or Concur OAuth

**What it is**: Instead of file uploads, the platform would pull data directly from SAP via its OData API (or BAPI), and from Concur via its REST API (OAuth 2.0), on a schedule (daily, weekly). No human in the loop for the data transfer step.

**Why we didn't build it**: Both APIs require credentials and configuration that cannot be provisioned for a prototype:
- **SAP OData**: Requires BASIS team to activate the OData service, configure authentication (usually client certificates or SAML), and whitelist the platform's IP. Timeline: weeks. SAP also throttles OData requests heavily on-prem.
- **Concur API**: Requires OAuth 2.0 registration by the client's Concur administrator, approval from SAP Concur's partner program, and company-specific scopes. Timeline: 2-4 weeks minimum.

**The real cost**: Even if we had credentials, building a reliable poll-and-deduplicate ingestion pipeline with backfill handling, rate limiting, and error recovery is a week of work by itself — not counting the credential setup.

**What we built instead**: File upload with idempotent re-ingestion support (`source_row_id` deduplication) and a `DataSource.config` structure ready to store API credentials when the time comes. Adding an API ingestion path is an extension, not a rewrite.

**What would change in production**: An async worker (Celery + Redis, or a cron-triggered Cloud Run job) would call the SAP OData endpoint for new material documents since the last run, parse the response (same parser logic, different input), and create `EmissionRecord` instances. The review dashboard is unchanged.

---

## 3. Automated Emission Factor Updates and Versioning

**What it is**: Emission factor databases (DEFRA, EPA, IEA) publish updated values every year. An automated system would pull the latest factors, store them versioned in the database, and allow analysts to re-run the calculation on historical records using the new factors — with full audit trail.

**Why we didn't build it**: This is deceptively complex:
- Factor databases don't have public APIs — they're published as Excel downloads on government websites.
- Re-running calculations on approved records raises governance questions: who authorizes the re-run? Does it invalidate previous approvals? Which year's factors apply to which reporting period?
- The GHG Protocol says you should apply the factors available at the time of reporting, not retroactively update previous years. So a 2023 emissions report should use DEFRA 2023 factors, even if calculated in 2025.

**What we built instead**: The `emission_factor_used` field stores a human-readable string describing the factor source and version (e.g., "DEFRA 2023 – Fuel combustion: diesel, per litre"). This makes every record self-documenting: you can always determine which version was used without looking at code. When we update to DEFRA 2024, we update the constants in `emission_factors.py` and all new records use the new factors. Historical records retain the old factor string — which is correct behaviour.

**What would change in production**: A `EmissionFactor` model with (source, version, category, value) and a FK from `EmissionRecord`. The parser looks up the factor from the DB at ingestion time. Updates to the DB create new factor rows, not updates to existing ones. Analysts can compare year-over-year factor changes through a dedicated UI.
