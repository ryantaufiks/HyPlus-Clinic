from django.urls import path

from . import views

app_name = "kiosk"

urlpatterns = [
    # Main kiosk interface
    path("", views.HomeView.as_view(), name="home"),
    # API endpoints
    path(
        "api/patients/", views.PatientCreateAPIView.as_view(), name="api-patient-create"
    ),
    path(
        "api/measurements/",
        views.MeasurementCreateAPIView.as_view(),
        name="api-measurement-create",
    ),
    path(
        "api/queue/generate/",
        views.QueueGenerateAPIView.as_view(),
        name="api-queue-generate",
    ),
    # Patient management
    path("patients/", views.PatientListView.as_view(), name="patient-list"),
    path(
        "patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"
    ),
    # Queue tickets
    path(
        "ticket/<uuid:qr_code>/",
        views.QueueTicketDetailView.as_view(),
        name="ticket-detail",
    ),
    # Dashboard and QR scanner
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("scanner/", views.QRScannerView.as_view(), name="qr-scanner"),
    # Test page for Three.js visualizations
    path(
        "test-visualizations/",
        views.TestVisualizationsView.as_view(),
        name="test-visualizations",
    ),
]
