from django.urls import path
from . import views

urlpatterns = [
    path("sources/", views.DataSourceListView.as_view(), name="datasource-list"),
    path("runs/", views.IngestionRunListView.as_view(), name="ingestion-run-list"),
    path("runs/<int:pk>/", views.IngestionRunDetailView.as_view(), name="ingestion-run-detail"),
    path("upload/", views.UploadView.as_view(), name="ingestion-upload"),
]
