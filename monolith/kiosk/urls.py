from django.urls import path

from . import accounts_views, avatar_views, clinical_views, device_views, kiosk_api, portal_views, queue_views, views

app_name = "kiosk"

urlpatterns = [
    # Kiosk
    path("", views.HomeView.as_view(), name="home"),
    path("api/kiosk/lookup/", kiosk_api.PatientLookupView.as_view(), name="api-patient-lookup"),
    path("api/kiosk/visits/", kiosk_api.VisitStartView.as_view(), name="api-visit-start"),
    path("api/kiosk/visits/<uuid:token>/finish/", kiosk_api.VisitFinishView.as_view(), name="api-visit-finish"),
    path(
        "api/kiosk/visits/<uuid:token>/simulated-measurement/",
        kiosk_api.SimulatedMeasurementView.as_view(),
        name="api-simulated-measurement",
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
    # Ticket QR code: the visit for staff, the registration form for the patient
    path("v/<uuid:token>/", clinical_views.VisitTokenView.as_view(), name="visit-token"),
    path("v/<uuid:token>/status/", queue_views.VisitStatusView.as_view(), name="visit-status"),
    path("v/<uuid:token>/qr.png", queue_views.ticket_qr_png, name="visit-qr"),
    # Waiting-room TV (public: queue numbers and rooms only)
    path("display/", queue_views.DisplayView.as_view(), name="display"),
    path("display/data/", queue_views.DisplayDataView.as_view(), name="display-data"),
    path("ticket/<uuid:qr_code>/", clinical_views.legacy_ticket_redirect, name="ticket-detail"),
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
    # Patients and registration
    path("patients/", views.PatientListView.as_view(), name="patient-list"),
    path("patients/new/", clinical_views.PatientRegisterView.as_view(), name="patient-register"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),
    path("patients/<int:pk>/edit/", clinical_views.PatientEditView.as_view(), name="patient-edit"),
    path("patients/<int:pk>/merge/", clinical_views.PatientMergeView.as_view(), name="patient-merge"),
    path("patients/<int:pk>/portal/invite/", portal_views.PortalInviteView.as_view(), name="patient-portal-invite"),
    path("patients/<int:pk>/portal/disable/", portal_views.PortalDisableView.as_view(), name="patient-portal-disable"),
    path("registrations/", clinical_views.SubmissionListView.as_view(), name="submissions"),
    path(
        "registrations/<int:pk>/review/",
        clinical_views.SubmissionReviewView.as_view(),
        name="submission-review",
    ),
    # Profile photos (served after a permission check, never public)
    path("me/", avatar_views.MyProfileView.as_view(), name="my-profile"),
    path("photos/staff/<int:user_id>/", avatar_views.staff_photo, name="staff-photo"),
    path("photos/patients/<int:pk>/", avatar_views.patient_photo, name="patient-photo"),
    # Staff accounts (administrators)
    path("staff/", accounts_views.StaffListView.as_view(), name="staff-list"),
    path("staff/new/", accounts_views.StaffCreateView.as_view(), name="staff-create"),
    path("staff/<int:pk>/", accounts_views.StaffEditView.as_view(), name="staff-edit"),
    # Doctor
    path("doctor/", clinical_views.DoctorQueueView.as_view(), name="doctor-queue"),
    path("doctor/call-next/", queue_views.CallNextView.as_view(), name="call-next"),
    path("doctor/duty/", queue_views.DutyView.as_view(), name="doctor-duty"),
    path("visits/<int:pk>/call/", queue_views.CallView.as_view(), name="visit-call"),
    path("visits/<int:pk>/cancel/", queue_views.CancelVisitView.as_view(), name="visit-cancel"),
    path("visits/<int:pk>/", clinical_views.VisitDetailView.as_view(), name="visit-detail"),
    path(
        "visits/<int:pk>/prescription/",
        clinical_views.PrescriptionPrintView.as_view(),
        name="prescription-print",
    ),
    # Dashboard and QR scanner
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("dashboard/data/", views.DashboardDataView.as_view(), name="dashboard-data"),
    # Access control at the consulting-room door
    path("scanner/", queue_views.AccessControlView.as_view(), name="qr-scanner"),
    path("api/access/admit/", queue_views.AdmitView.as_view(), name="api-access-admit"),
]
