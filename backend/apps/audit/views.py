from rest_framework.views import APIView
from rest_framework.response import Response
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(APIView):
    def get(self, request):
        tenant = request.user.profile.tenant
        qs = AuditLog.objects.filter(tenant=tenant).select_related(
            "actor", "emission_record", "ingestion_run"
        )

        if run_id := request.query_params.get("run_id"):
            qs = qs.filter(ingestion_run_id=run_id)
        if record_id := request.query_params.get("record_id"):
            qs = qs.filter(emission_record_id=record_id)

        page = int(request.query_params.get("page", 1))
        page_size = 50
        total = qs.count()
        qs_page = qs[(page - 1) * page_size: page * page_size]

        return Response({
            "count": total,
            "page": page,
            "results": AuditLogSerializer(qs_page, many=True).data,
        })
