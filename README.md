# BreatheESG — Emissions Data Ingestion Platform

A Django REST + React prototype for ingesting, normalizing, and reviewing emissions data from three enterprise source types.

## Live Demo

- **Frontend**: https://breatheesg.vercel.app *(deploy in progress)*
- **Backend API**: https://breatheesg-backend.up.railway.app *(deploy in progress)*
- **Demo login**: `analyst@acme.com` / `analyst123`

## Project Structure

```
breatheesg/
├── backend/               # Django REST API
│   ├── apps/
│   │   ├── tenants/       # Tenant + UserProfile models, auth
│   │   ├── ingestion/     # DataSource, IngestionRun, parsers
│   │   ├── records/       # EmissionRecord model + review API
│   │   └── audit/         # AuditLog model
│   └── requirements.txt
├── frontend/              # Vite + React + Tailwind
│   └── src/
│       ├── pages/         # Dashboard, Ingest, Review, AuditLog
│       └── components/    # Layout
├── sample_data/           # Realistic CSV files for seeding
│   ├── sap_mb51_export.csv
│   ├── utility_portal_export.csv
│   └── concur_expense_extract.csv
├── MODEL.md               # Data model and design rationale
├── DECISIONS.md           # Every ambiguity resolved
├── TRADEOFFS.md           # Three things not built and why
└── SOURCES.md             # Per-source research and sample data rationale
```

## Running Locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo  # Creates demo tenant, user, and loads sample data
python manage.py runserver
```

API available at `http://localhost:8000/api/`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`

## Three Data Sources

| Source | Format | Ingestion |
|---|---|---|
| SAP MB51 | CSV (German headers, German locale) | File upload |
| Utility Portal | CSV (Green Button / portal export) | File upload |
| Concur SAE | CSV (Standard Accounting Extract) | File upload |

## Key Design Decisions

- **One record per source row** — granularity preserved for audit traceability
- **`raw_row` JSONField** — original source data always recoverable
- **Stored `co2e_kg`** with `emission_factor_used` string — factor version provenance
- **Immutable AuditLog** with before/after state snapshots
- **Row-level multi-tenancy** via `tenant` FK on every model
- **Parser-set anomaly flags** — `needs_review` surfaced automatically to analysts

See [MODEL.md](MODEL.md), [DECISIONS.md](DECISIONS.md), [TRADEOFFS.md](TRADEOFFS.md), [SOURCES.md](SOURCES.md) for full documentation.

## Emission Factor Sources

- UK DEFRA/DESNZ Greenhouse Gas Conversion Factors 2023
- IEA 2022 National Grid Emission Factors
- Cornell Hotel Sustainability Benchmarking Index 2023

## Tech Stack

- **Backend**: Django 5 + Django REST Framework
- **Database**: PostgreSQL (Railway) / SQLite (local)
- **Frontend**: Vite + React 18 + TypeScript + Tailwind CSS
- **Data fetching**: TanStack Query v5
- **Charts**: Recharts
- **Deployment**: Railway (backend) + Vercel (frontend)
