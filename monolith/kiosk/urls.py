from django.urls import path

from . import device_views, views

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
    path("api/devices/wait/", device_views.DeviceWaitView.as_view(), name="api-device-wait"),
    path(
        "api/devices/readings/latest/",
        device_views.LatestDeviceReadingView.as_view(),
        name="api-device-reading-latest",
    ),
    path(
        "api/devices/readings/<int:pk>/claim/",
        device_views.ClaimDeviceReadingView.as_view(),
        name="api-device-reading-claim",
    ),
    # Internal API for the BLE gateway (bearer token)
    path(
        "internal/gateway/heartbeat/",
        device_views.GatewayHeartbeatView.as_view(),
        name="internal-gateway-heartbeat",
    ),
    path(
        "internal/device-readings/",
        device_views.DeviceReadingIngestView.as_view(),
        name="internal-device-reading",
    ),
    path(
        "internal/gateway/commands/<int:pk>/",
        device_views.GatewayCommandResultView.as_view(),
        name="internal-gateway-command-result",
    ),
    # Staff device management
    path("devices/", device_views.DevicesPageView.as_view(), name="devices"),
    path("devices/status/", device_views.DeviceStatusView.as_view(), name="devices-status"),
    path("devices/commands/", device_views.DeviceCommandCreateView.as_view(), name="devices-command-create"),
    path(
        "devices/commands/<int:pk>/",
        device_views.DeviceCommandDetailView.as_view(),
        name="devices-command-detail",
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
