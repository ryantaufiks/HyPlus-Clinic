import base64
import io
import json
import logging

import qrcode
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import DetailView, ListView, TemplateView
from django_ratelimit.decorators import ratelimit

from .models import Measurement, Patient, QueueTicket

logger = logging.getLogger(__name__)

kiosk_api_ratelimit = method_decorator(
    ratelimit(key="ip", rate=settings.KIOSK_API_RATE, method="POST", block=True),
    name="post",
)


def server_error(message):
    logger.exception(message)
    return JsonResponse({"error": "Internal server error"}, status=500)


def healthz(request):
    """Liveness/readiness probe used by Docker."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(TemplateView):
    """Main kiosk interface"""

    template_name = "kiosk/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "AIVIN"
        return context


@kiosk_api_ratelimit
class PatientCreateAPIView(View):
    """API endpoint to create a new patient"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            name = data.get("name")
            symptoms = data.get("symptoms")

            if not name or not symptoms:
                return JsonResponse(
                    {"error": "Name and symptoms are required"}, status=400
                )

            patient = Patient.objects.create(name=name, symptoms=symptoms)

            return JsonResponse(
                {
                    "id": patient.id,
                    "name": patient.name,
                    "symptoms": patient.symptoms,
                    "created_at": patient.created_at.isoformat(),
                },
                status=201,
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Http404:
            raise
        except Exception:
            return server_error("Failed to create patient")


@kiosk_api_ratelimit
class MeasurementCreateAPIView(View):
    """API endpoint to create a new measurement"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            patient_id = data.get("patient_id") or data.get("patient")

            if not patient_id:
                return JsonResponse({"error": "Patient ID is required"}, status=400)

            patient = get_object_or_404(Patient, id=patient_id)

            measurement = Measurement.objects.create(
                patient=patient,
                weight_kg=data.get("weight_kg"),
                systolic_bp=data.get("systolic_bp"),
                diastolic_bp=data.get("diastolic_bp"),
                heart_rate_bpm=data.get("heart_rate_bpm"),
            )

            return JsonResponse(
                {
                    "id": measurement.id,
                    "patient_id": patient.id,
                    "weight_kg": measurement.weight_kg,
                    "systolic_bp": measurement.systolic_bp,
                    "diastolic_bp": measurement.diastolic_bp,
                    "heart_rate_bpm": measurement.heart_rate_bpm,
                    "measured_at": measurement.measured_at.isoformat(),
                },
                status=201,
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Http404:
            raise
        except Exception:
            return server_error("Failed to create measurement")


@kiosk_api_ratelimit
class QueueGenerateAPIView(View):
    """API endpoint to generate a queue ticket"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            patient_id = data.get("patient_id")

            if not patient_id:
                return JsonResponse({"error": "Patient ID is required"}, status=400)

            patient = get_object_or_404(Patient, id=patient_id)

            # Generate a unique queue number
            last_ticket = QueueTicket.objects.order_by("-id").first()
            if last_ticket and last_ticket.queue_number:
                # Extract the number part and increment
                last_num = int(last_ticket.queue_number[1:])
                new_num = last_num + 1
                new_queue_number = f"A{new_num:03d}"
            else:
                new_queue_number = "A001"

            # Create the queue ticket
            ticket = QueueTicket.objects.create(
                patient=patient, queue_number=new_queue_number
            )

            # Generate QR code as base64 image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(str(ticket.qr_code_data))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            qr_code_base64 = f"data:image/png;base64,{img_str}"

            return JsonResponse(
                {
                    "id": ticket.id,
                    "patient_id": patient.id,
                    "queue_number": ticket.queue_number,
                    "qr_code_data": str(ticket.qr_code_data),
                    "qr_code_image": qr_code_base64,
                    "is_active": ticket.is_active,
                    "created_at": ticket.created_at.isoformat(),
                },
                status=201,
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Http404:
            raise
        except Exception:
            return server_error("Failed to generate queue ticket")


class PatientListView(LoginRequiredMixin, ListView):
    """List all patients"""

    model = Patient
    template_name = "kiosk/patient_list.html"
    context_object_name = "patients"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("queue_tickets")
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


class PatientDetailView(LoginRequiredMixin, DetailView):
    """View patient details with measurements and queue tickets"""

    model = Patient
    template_name = "kiosk/patient_detail.html"
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["measurements"] = self.object.measurements.all()
        context["queue_tickets"] = self.object.queue_tickets.all()

        # Get latest measurement for health data visualization
        latest_measurement = self.object.measurements.order_by("-measured_at").first()
        context["latest_measurement"] = latest_measurement

        # Get last visit date
        if context["measurements"].count() > 1:
            context["last_visit"] = context["measurements"][1].measured_at
        else:
            context["last_visit"] = None

        return context


class QueueTicketDetailView(LoginRequiredMixin, DetailView):
    """View queue ticket details"""

    model = QueueTicket
    template_name = "kiosk/queue_ticket.html"
    context_object_name = "ticket"
    slug_field = "qr_code_data"
    slug_url_kwarg = "qr_code"

    def get_object(self, queryset=None):
        qr_code = self.kwargs.get("qr_code")
        return get_object_or_404(QueueTicket, qr_code_data=qr_code)


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for viewing all data"""

    template_name = "kiosk/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_patients"] = Patient.objects.count()
        context["total_measurements"] = Measurement.objects.count()
        context["active_tickets"] = QueueTicket.objects.filter(is_active=True).count()
        context["recent_patients"] = Patient.objects.all()[:10]
        context["recent_tickets"] = QueueTicket.objects.filter(is_active=True)[:10]

        # Get latest measurement for health data visualization
        latest_measurement = Measurement.objects.order_by("-measured_at").first()
        if latest_measurement:
            context["heart_rate"] = latest_measurement.heart_rate_bpm
            context["systolic"] = latest_measurement.systolic_bp
            context["diastolic"] = latest_measurement.diastolic_bp
            context["weight"] = latest_measurement.weight_kg
            context["oxygen_saturation"] = getattr(
                latest_measurement, "oxygen_saturation", 98
            )
        else:
            # Default values if no measurements exist
            context["heart_rate"] = 72
            context["systolic"] = 120
            context["diastolic"] = 80
            context["weight"] = 70
            context["oxygen_saturation"] = 98

        return context


class QRScannerView(LoginRequiredMixin, TemplateView):
    """QR code scanner for doctors"""

    template_name = "kiosk/qr_scanner.html"


class TestVisualizationsView(LoginRequiredMixin, TemplateView):
    """Test page for Three.js visualizations"""

    template_name = "kiosk/test-visualizations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Three.js Visualization Test"
        return context
