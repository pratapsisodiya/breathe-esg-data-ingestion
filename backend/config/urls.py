from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    return JsonResponse({"status": "ok", "version": "1.0.0"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check),
    path("api/auth/", include("apps.tenants.urls")),
    path("api/ingestion/", include("apps.ingestion.urls")),
    path("api/records/", include("apps.records.urls")),
    path("api/audit/", include("apps.audit.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
