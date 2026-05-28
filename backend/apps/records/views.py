from datetime import datetime, timezone
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.utils import timezone as dj_timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.ingestion.parsers import emission_factors as ef
from .models import EmissionRecord
from .serializers import EmissionRecordSerializer, EmissionRecordListSerializer


def _record_snapshot(record: EmissionRecord) -> dict:
    """Capture fields that analysts can change, for before/after audit snapshots."""
    return {
        "status": record.status,
        "review_note": record.review_note,
        "activity_quantity": str(record.activity_quantity),
        "activity_unit": record.activity_unit,
        "co2e_kg": str(record.co2e_kg) if record.co2e_kg is not None else None,
    }


class EmissionRecordListView(APIView):
    """
    List and filter EmissionRecords for the current tenant.

    Query params:
      status, scope, source_type, needs_review, run_id, period_start, period_end
    """

    def get(self, request):
        qs = EmissionRecord.objects.filter(tenant=request.user.profile.tenant)

        # Filters
        if status := request.query_params.get("status"):
            qs = qs.filter(status=status)
        if scope := request.query_params.get("scope"):
            qs = qs.filter(scope=scope)
        if source_type := request.query_params.get("source_type"):
            qs = qs.filter(source_type=source_type)
        if request.query_params.get("needs_review") == "true":
            qs = qs.filter(needs_review=True)
        if run_id := request.query_params.get("run_id"):
            qs = qs.filter(ingestion_run_id=run_id)
        if p_start := request.query_params.get("period_start"):
            qs = qs.filter(period_start__gte=p_start)
        if p_end := request.query_params.get("period_end"):
            qs = qs.filter(period_end__lte=p_end)

        page = int(request.query_params.get("page", 1))
        page_size = 50
        total = qs.count()
        qs_page = qs[(page - 1) * page_size: page * page_size]

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": EmissionRecordListSerializer(qs_page, many=True).data,
        })


def recompute_record_emissions(rec: EmissionRecord):
    """
    Recalculates normalized quantities and co2e emissions when an analyst
    modifies activity_quantity or activity_unit.
    """
    qty = Decimal(str(rec.activity_quantity))
    unit = str(rec.activity_unit).strip().upper()

    qty_norm = qty
    unit_norm = rec.unit_normalized

    if rec.source_type == "SAP_FUEL":
        mapped = ef.SAP_UNIT_MAP.get(unit, unit)
        if unit == "G":
            qty_norm = qty / Decimal("1000")
            unit_norm = "KG"
        elif unit == "T":
            qty_norm = qty * Decimal("1000")
            unit_norm = "KG"
        else:
            qty_norm = qty
            unit_norm = mapped

    elif rec.source_type == "UTILITY":
        if unit in ("MWH", "MW·H", "MEGAWATT-HOUR"):
            qty_norm = qty * Decimal("1000")
            unit_norm = "kWh"
        elif unit in ("GWH", "GIGAWATT-HOUR"):
            qty_norm = qty * Decimal("1000000")
            unit_norm = "kWh"
        else:
            qty_norm = qty
            unit_norm = "kWh"

    elif rec.source_type == "CONCUR":
        if unit in ("MILES", "MI"):
            qty_norm = qty * Decimal("1.60934")
            unit_norm = "km"
        else:
            qty_norm = qty
            unit_norm = rec.unit_normalized

    rec.quantity_normalized = qty_norm.quantize(Decimal("0.0001"))
    rec.unit_normalized = unit_norm

    if rec.emission_factor_value is not None:
        rec.co2e_kg = (qty_norm * Decimal(str(rec.emission_factor_value))).quantize(Decimal("0.0001"))
    else:
        rec.co2e_kg = None


class EmissionRecordDetailView(APIView):
    def _get_record(self, request, pk):
        try:
            return EmissionRecord.objects.get(pk=pk, tenant=request.user.profile.tenant)
        except EmissionRecord.DoesNotExist:
            return None

    def get(self, request, pk):
        rec = self._get_record(request, pk)
        if not rec:
            return Response({"error": "Not found"}, status=404)
        return Response(EmissionRecordSerializer(rec).data)

    def patch(self, request, pk):
        """Analyst can edit review_note, activity_quantity, activity_unit."""
        rec = self._get_record(request, pk)
        if not rec:
            return Response({"error": "Not found"}, status=404)
        if rec.is_locked:
            return Response({"error": "Record is locked for audit"}, status=403)

        before = _record_snapshot(rec)
        editable = ["review_note", "activity_quantity", "activity_unit"]
        
        # Verify that activity_quantity is a valid number if provided
        if "activity_quantity" in request.data:
            try:
                Decimal(str(request.data["activity_quantity"]))
            except Exception:
                return Response({"error": "Invalid activity quantity format"}, status=400)

        for field in editable:
            if field in request.data:
                setattr(rec, field, request.data[field])

        # Recalculate normalizations and emissions
        try:
            recompute_record_emissions(rec)
        except Exception as e:
            return Response({"error": f"Error performing recalculations: {str(e)}"}, status=400)

        rec.save(update_fields=editable + ["quantity_normalized", "unit_normalized", "co2e_kg", "updated_at"])

        AuditLog.log(
            tenant=request.user.profile.tenant,
            action=AuditLog.Action.RECORD_EDITED,
            actor=request.user,
            emission_record=rec,
            before_state=before,
            after_state=_record_snapshot(rec),
            description=f"Record #{rec.id} edited",
        )
        return Response(EmissionRecordSerializer(rec).data)



class ApproveRecordView(APIView):
    def post(self, request, pk):
        try:
            rec = EmissionRecord.objects.get(pk=pk, tenant=request.user.profile.tenant)
        except EmissionRecord.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        if rec.is_locked:
            return Response({"error": "Record is locked"}, status=403)

        before = _record_snapshot(rec)
        rec.status = EmissionRecord.Status.APPROVED
        rec.reviewed_by = request.user
        rec.reviewed_at = dj_timezone.now()
        rec.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

        AuditLog.log(
            tenant=request.user.profile.tenant,
            action=AuditLog.Action.RECORD_APPROVED,
            actor=request.user,
            emission_record=rec,
            before_state=before,
            after_state=_record_snapshot(rec),
            description=f"Record #{rec.id} approved",
        )
        return Response(EmissionRecordSerializer(rec).data)


class FlagRecordView(APIView):
    def post(self, request, pk):
        try:
            rec = EmissionRecord.objects.get(pk=pk, tenant=request.user.profile.tenant)
        except EmissionRecord.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        if rec.is_locked:
            return Response({"error": "Record is locked"}, status=403)

        before = _record_snapshot(rec)
        rec.status = EmissionRecord.Status.FLAGGED
        rec.review_note = request.data.get("note", rec.review_note)
        rec.reviewed_by = request.user
        rec.reviewed_at = dj_timezone.now()
        rec.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])

        AuditLog.log(
            tenant=request.user.profile.tenant,
            action=AuditLog.Action.RECORD_FLAGGED,
            actor=request.user,
            emission_record=rec,
            before_state=before,
            after_state=_record_snapshot(rec),
            description=f"Record #{rec.id} flagged: {rec.review_note}",
        )
        return Response(EmissionRecordSerializer(rec).data)


class RejectRecordView(APIView):
    def post(self, request, pk):
        try:
            rec = EmissionRecord.objects.get(pk=pk, tenant=request.user.profile.tenant)
        except EmissionRecord.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        if rec.is_locked:
            return Response({"error": "Record is locked"}, status=403)

        before = _record_snapshot(rec)
        rec.status = EmissionRecord.Status.REJECTED
        rec.review_note = request.data.get("note", rec.review_note)
        rec.reviewed_by = request.user
        rec.reviewed_at = dj_timezone.now()
        rec.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])

        AuditLog.log(
            tenant=request.user.profile.tenant,
            action=AuditLog.Action.RECORD_REJECTED,
            actor=request.user,
            emission_record=rec,
            before_state=before,
            after_state=_record_snapshot(rec),
            description=f"Record #{rec.id} rejected",
        )
        return Response(EmissionRecordSerializer(rec).data)


class BulkApproveView(APIView):
    """Approve all PENDING records in a given ingestion run."""

    def post(self, request):
        run_id = request.data.get("run_id")
        if not run_id:
            return Response({"error": "run_id required"}, status=400)

        tenant = request.user.profile.tenant
        qs = EmissionRecord.objects.filter(
            tenant=tenant,
            ingestion_run_id=run_id,
            status=EmissionRecord.Status.PENDING,
            is_locked=False,
        )
        count = qs.count()
        now = dj_timezone.now()
        qs.update(
            status=EmissionRecord.Status.APPROVED,
            reviewed_by_id=request.user.id,
            reviewed_at=now,
        )

        AuditLog.log(
            tenant=tenant,
            action=AuditLog.Action.BULK_APPROVED,
            actor=request.user,
            description=f"Bulk approved {count} records from run #{run_id}",
        )
        return Response({"approved": count})


class SummaryView(APIView):
    """Aggregated tCO2e totals by scope, source, and period."""

    def get(self, request):
        tenant = request.user.profile.tenant
        qs = EmissionRecord.objects.filter(
            tenant=tenant,
            status__in=[EmissionRecord.Status.PENDING, EmissionRecord.Status.APPROVED],
        )

        by_scope = {}
        for scope in EmissionRecord.Scope.values:
            total = qs.filter(scope=scope).aggregate(t=Sum("co2e_kg"))["t"] or 0
            by_scope[scope] = round(total / 1000, 3)  # convert to tonnes

        by_source = {}
        for src in EmissionRecord.SourceType.values:
            total = qs.filter(source_type=src).aggregate(t=Sum("co2e_kg"))["t"] or 0
            by_source[src] = round(total / 1000, 3)

        pending_count = qs.filter(status=EmissionRecord.Status.PENDING).count()
        flagged_count = qs.filter(needs_review=True).count()

        return Response({
            "by_scope": by_scope,
            "by_source": by_source,
            "pending_count": pending_count,
            "flagged_count": flagged_count,
            "total_tco2e": sum(by_scope.values()),
        })
