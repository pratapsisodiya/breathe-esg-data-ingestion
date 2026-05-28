"""
Management command: seed_demo

Creates a demo tenant, analyst user, three data sources, and parses the
sample CSV files from the sample_data/ directory to populate the database
with realistic data for the live demo.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --no-input   (non-interactive, for Procfile)
    python manage.py seed_demo --force      (re-seeds even if data exists)
"""

import os
import sys
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from rest_framework.authtoken.models import Token

from apps.tenants.models import Tenant, UserProfile
from apps.ingestion.models import DataSource, IngestionRun
from apps.ingestion.parsers import PARSER_MAP
from apps.records.models import EmissionRecord
from apps.audit.models import AuditLog
from django.utils import timezone


SAMPLE_DIR = Path(__file__).resolve().parents[5] / "sample_data"

DEMO_TENANT = "Acme Manufacturing GmbH"
DEMO_USER_EMAIL = "analyst@acme.com"
DEMO_PASSWORD = "analyst123"

DATA_SOURCES = [
    {
        "name": "SAP ERP – Fuel & Procurement",
        "source_type": "SAP_FUEL",
        "file": "sap_mb51_export.csv",
        "config": {
            "plant_lookup": {
                "DE01": {"country": "DE", "site": "Stuttgart Plant"},
                "IN02": {"country": "IN", "site": "Pune Factory"},
                "US03": {"country": "US", "site": "Detroit Assembly"},
            }
        },
    },
    {
        "name": "Utility Portals – Electricity",
        "source_type": "UTILITY",
        "file": "utility_portal_export.csv",
        "config": {
            "meter_lookup": {
                "MTR-001": {"country": "DE", "site": "Stuttgart HQ"},
                "MTR-002": {"country": "IN", "site": "Pune Factory"},
                "MTR-003": {"country": "US", "site": "Detroit Assembly"},
            }
        },
    },
    {
        "name": "Concur – Business Travel",
        "source_type": "CONCUR",
        "file": "concur_expense_extract.csv",
        "config": {"default_country": "DE"},
    },
]


class Command(BaseCommand):
    help = "Seed demo tenant, user, and sample emission data"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-seed even if data exists")
        parser.add_argument("--no-input", action="store_true", help="Non-interactive mode")

    def handle(self, *args, **options):
        if Tenant.objects.filter(slug="acme-manufacturing").exists() and not options["force"]:
            self.stdout.write(self.style.WARNING("Demo data already exists. Use --force to re-seed."))
            return

        self.stdout.write("Seeding demo data...")

        # Create tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug="acme-manufacturing",
            defaults={"name": DEMO_TENANT},
        )
        self.stdout.write(f"  [OK] Tenant: {tenant.name}")

        # Create analyst user
        user, created = User.objects.get_or_create(
            username="analyst",
            defaults={
                "email": DEMO_USER_EMAIL,
                "first_name": "Priya",
                "last_name": "Sharma",
            },
        )
        if created or options["force"]:
            user.set_password(DEMO_PASSWORD)
            user.save()
        UserProfile.objects.get_or_create(user=user, defaults={"tenant": tenant, "role": "analyst"})
        Token.objects.get_or_create(user=user)
        self.stdout.write(f"  [OK] User: {DEMO_USER_EMAIL} / {DEMO_PASSWORD}")

        # Create admin superuser
        admin_user, admin_created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@acme.com",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin_created or options["force"]:
            admin_user.set_password("admin123")
            admin_user.save()
        self.stdout.write(f"  [OK] Superuser: admin / admin123")

        # Process each data source
        for ds_config in DATA_SOURCES:
            source, _ = DataSource.objects.get_or_create(
                tenant=tenant,
                source_type=ds_config["source_type"],
                defaults={
                    "name": ds_config["name"],
                    "config": ds_config["config"],
                },
            )

            sample_file = SAMPLE_DIR / ds_config["file"]
            if not sample_file.exists():
                self.stdout.write(
                    self.style.WARNING(f"  [WARN] Sample file not found: {sample_file}")
                )
                continue

            parse_fn = PARSER_MAP[ds_config["source_type"]]
            try:
                result = parse_fn(str(sample_file), ds_config["config"])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [ERROR] Parse error for {ds_config['file']}: {e}"))
                continue

            parsed = result.get("records", [])
            errors = result.get("errors", [])

            run = IngestionRun.objects.create(
                data_source=source,
                triggered_by=user,
                status=IngestionRun.Status.DONE,
                original_filename=ds_config["file"],
                rows_total=len(parsed) + len(errors),
                rows_ok=len(parsed),
                rows_failed=len(errors),
                rows_flagged=sum(1 for r in parsed if r.get("needs_review")),
                error_log=errors,
                completed_at=timezone.now(),
            )

            AuditLog.log(
                tenant=tenant,
                action=AuditLog.Action.INGESTION_COMPLETED,
                actor=user,
                ingestion_run=run,
                description=f"Seed: {ds_config['file']} — {len(parsed)} records",
            )

            for rec_data in parsed:
                EmissionRecord.objects.create(
                    tenant=tenant,
                    ingestion_run=run,
                    source_type=rec_data["source_type"],
                    scope=rec_data["scope"],
                    category=rec_data["category"],
                    activity_description=rec_data["activity_description"],
                    activity_quantity=rec_data.get("activity_quantity") or 0,
                    activity_unit=rec_data.get("activity_unit", ""),
                    quantity_normalized=rec_data.get("quantity_normalized") or 0,
                    unit_normalized=rec_data.get("unit_normalized", ""),
                    emission_factor_used=rec_data.get("emission_factor_used", ""),
                    emission_factor_value=rec_data.get("emission_factor_value"),
                    co2e_kg=rec_data.get("co2e_kg"),
                    period_start=rec_data["period_start"],
                    period_end=rec_data["period_end"],
                    location=rec_data.get("location", ""),
                    location_country=rec_data.get("location_country", ""),
                    raw_row=rec_data.get("raw_row", {}),
                    source_row_id=rec_data.get("source_row_id", ""),
                    needs_review=rec_data.get("needs_review", False),
                    needs_review_reason=rec_data.get("needs_review_reason", ""),
                )

            self.stdout.write(
                f"  [OK] {ds_config['name']}: {len(parsed)} records, {len(errors)} errors"
            )

        self.stdout.write(self.style.SUCCESS("\nDemo seed complete!"))
        self.stdout.write(f"  Login: {DEMO_USER_EMAIL} / {DEMO_PASSWORD}")
