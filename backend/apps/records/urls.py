from django.urls import path
from . import views

urlpatterns = [
    path("", views.EmissionRecordListView.as_view(), name="record-list"),
    path("summary/", views.SummaryView.as_view(), name="record-summary"),
    path("bulk-approve/", views.BulkApproveView.as_view(), name="record-bulk-approve"),
    path("<int:pk>/", views.EmissionRecordDetailView.as_view(), name="record-detail"),
    path("<int:pk>/approve/", views.ApproveRecordView.as_view(), name="record-approve"),
    path("<int:pk>/flag/", views.FlagRecordView.as_view(), name="record-flag"),
    path("<int:pk>/reject/", views.RejectRecordView.as_view(), name="record-reject"),
]
