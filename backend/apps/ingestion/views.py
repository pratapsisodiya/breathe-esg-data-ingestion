import os
from datetime import datetime, timezone

from django.utils import timezone as dj_timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.records.models import EmissionRecord
from .models import DataSource, IngestionRun
from .parsers import PARSER_MAP
from .serializers import IngestionRunSerializer, DataSourceSerializer


class DataSourceListView(APIView):
    """List data sources for the current tenant."""

    def get(self, request):
        sources = DataSource.objects.filter(tenant=request.user.profile.tenant)
        return Response(DataSourceSerializer(sources, many=True).data)


class IngestionRunListView(APIView):
    """List ingestion runs for the current tenant."""

    def get(self, request):
        runs = IngestionRun.objects.filter(
            data_source__tenant=request.user.profile.tenant
        ).select_related("data_source", "triggered_by")
        # Wrap in {results: [...]} to match frontend expectation (same shape as records API)
        return Response({"results": IngestionRunSerializer(runs, many=True).data})


class IngestionRunDetailView(APIView):
    """Retrieve a single ingestion run including its error log."""

    def get(self, request, pk):
        try:
            run = IngestionRun.objects.get(
                pk=pk, data_source__tenant=request.user.profile.tenant
            )
        except IngestionRun.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response(IngestionRunSerializer(run).data)


class UploadView(APIView):
    """
    Accept a file upload for a given data source, run the appropriate parser,
    and persist all resulting EmissionRecords.

    POST /api/ingestion/upload/
    Form fields:
      - file: the CSV/XLSX file
      - source_id: DataSource pk
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        tenant = request.user.profile.tenant

        source_id = request.data.get("source_id")
        if not source_id:
            return Response({"error": "source_id is required"}, status=400)

        try:
            source = DataSource.objects.get(pk=source_id, tenant=tenant)
        except DataSource.DoesNotExist:
            return Response({"error": "DataSource not found"}, status=404)

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "file is required"}, status=400)

        # Create the run record
        run = IngestionRun.objects.create(
            data_source=source,
            triggered_by=request.user,
            status=IngestionRun.Status.RUNNING,
            original_filename=uploaded_file.name,
        )

        AuditLog.log(
            tenant=tenant,
            action=AuditLog.Action.INGESTION_STARTED,
            actor=request.user,
            ingestion_run=run,
            description=f"Ingestion started: {uploaded_file.name}",
        )

        # Save file to disk
        run.raw_file = uploaded_file
        run.save(update_fields=["raw_file"])

        file_path = run.raw_file.path
        parse_fn = PARSER_MAP.get(source.source_type)
        if not parse_fn:
            run.status = IngestionRun.Status.FAILED
            run.error_log = [{"error": f"No parser for source type: {source.source_type}"}]
            run.completed_at = dj_timezone.now()
            run.save()
            return Response({"error": "Unsupported source type"}, status=400)

        try:
            result = parse_fn(file_path, source.config)
        except Exception as exc:
            run.status = IngestionRun.Status.FAILED
            run.error_log = [{"error": str(exc)}]
            run.completed_at = dj_timezone.now()
            run.save()
            AuditLog.log(
                tenant=tenant,
                action=AuditLog.Action.INGESTION_FAILED,
                actor=request.user,
                ingestion_run=run,
                description=f"Parser crashed: {exc}",
            )
            return Response({"error": str(exc), "run_id": run.id}, status=422)

        # Persist records
        parsed_records = result.get("records", [])
        parse_errors = result.get("errors", [])
        created = []

        for rec_data in parsed_records:
            rec = EmissionRecord(
                tenant=tenant,
                ingestion_run=run,
                **{k: v for k, v in rec_data.items()
                   if k not in ("co2e_kg", "emission_factor_value", "activity_quantity",
                                "quantity_normalized")},
            )
            # Handle numeric fields carefully
            rec.activity_quantity = rec_data.get("activity_quantity") or 0
            rec.quantity_normalized = rec_data.get("quantity_normalized") or 0
            rec.co2e_kg = rec_data.get("co2e_kg")
            rec.emission_factor_value = rec_data.get("emission_factor_value")
            rec.save()
            created.append(rec)

        # Update run stats
        run.rows_total = len(parsed_records) + len(parse_errors)
        run.rows_ok = len(parsed_records)
        run.rows_failed = len(parse_errors)
        run.rows_flagged = sum(1 for r in parsed_records if r.get("needs_review"))
        run.error_log = parse_errors
        run.status = IngestionRun.Status.DONE
        run.completed_at = dj_timezone.now()
        run.save()

        AuditLog.log(
            tenant=tenant,
            action=AuditLog.Action.INGESTION_COMPLETED,
            actor=request.user,
            ingestion_run=run,
            description=(
                f"Ingestion completed: {run.rows_ok} OK, "
                f"{run.rows_failed} failed, {run.rows_flagged} flagged"
            ),
        )

        return Response(IngestionRunSerializer(run).data, status=201)
