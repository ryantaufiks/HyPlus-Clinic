import base64
import io
import json
import logging

import qrcode
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import DetailView, ListView, TemplateView
from django_ratelimit.decorators import ratelimit

from .device_views import gateway_devices, gateway_online
from .models import Measurement, Patient, QueueTicket
from .vitals import BP_CATEGORIES, bp_category, heart_rate_status

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
        context["simulation_enabled"] = settings.DEBUG
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
    """Record a simulated measurement. Only available with DEBUG on.

    Real measurements come from medical devices through the BLE gateway and
    are claimed via the device-reading API, never typed in by the kiosk.
    """

    def post(self, request):
        if not settings.DEBUG:
            return JsonResponse({"error": "Simulated measurements are disabled"}, status=403)
        try:
            data = json.loads(request.body)
            patient_id = data.get("patient_id") or data.get("patient")

            if not patient_id:
                return JsonResponse({"error": "Patient ID is required"}, status=400)

            patient = get_object_or_404(Patient, id=patient_id)

            measurement = Measurement.objects.create(
                patient=patient,
                source=Measurement.SOURCE_SIMULATED,
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


def latest_vitals(measurements):
    """Newest weight and newest blood pressure among `measurements` (newest first).

    The kiosk stores each device reading as its own Measurement, so a check-in
    usually has one row for weight and one for blood pressure.
    """
    vitals = {}
    for m in measurements:
        if "weight" not in vitals and m.weight_kg is not None:
            vitals["weight"] = m
        if "bp" not in vitals and m.systolic_bp is not None and m.diastolic_bp is not None:
            vitals["bp"] = m
        if len(vitals) == 2:
            break
    bp = vitals.get("bp")
    return {
        "weight": vitals.get("weight"),
        "bp": bp,
        "bp_category": bp_category(bp.systolic_bp, bp.diastolic_bp) if bp else None,
        "hr_status": heart_rate_status(bp.heart_rate_bpm) if bp else None,
    }


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "kiosk/patient_list.html"
    context_object_name = "patients"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("queue_tickets", "measurements")
        search = self.request.GET.get("search", "").strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "").strip()
        context["rows"] = [
            {"patient": p, "vitals": latest_vitals(p.measurements.all()), "ticket": next(iter(p.queue_tickets.all()), None)}
            for p in context["patients"]
        ]
        return context


class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = "kiosk/patient_detail.html"
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        measurements = list(self.object.measurements.order_by("-measured_at"))
        context["measurements"] = measurements
        context["queue_tickets"] = self.object.queue_tickets.order_by("-created_at")
        context["vitals"] = latest_vitals(measurements)
        oldest_first = list(reversed(measurements))
        context["chart_data"] = {
            "bp": [
                {"t": m.measured_at.isoformat(), "systolic": m.systolic_bp, "diastolic": m.diastolic_bp, "pulse": m.heart_rate_bpm}
                for m in oldest_first
                if m.systolic_bp is not None and m.diastolic_bp is not None
            ],
            "weight": [
                {"t": m.measured_at.isoformat(), "weight": m.weight_kg} for m in oldest_first if m.weight_kg is not None
            ],
        }
        return context


class QueueTicketDetailView(LoginRequiredMixin, DetailView):
    """The doctor's summary for a queue ticket, opened by scanning its QR code."""

    model = QueueTicket
    template_name = "kiosk/queue_ticket.html"
    context_object_name = "ticket"

    def get_object(self, queryset=None):
        return get_object_or_404(QueueTicket.objects.select_related("patient"), qr_code_data=self.kwargs["qr_code"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object.patient
        visit = patient.measurements.filter(measured_at__lte=self.object.created_at).order_by("-measured_at")
        context["vitals"] = latest_vitals(visit)
        context["previous_tickets"] = patient.queue_tickets.exclude(pk=self.object.pk).order_by("-created_at")[:5]
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Live overview for nurses and doctors; data comes from DashboardDataView."""

    template_name = "kiosk/dashboard.html"


class DashboardDataView(LoginRequiredMixin, View):
    """JSON for the dashboard, polled every few seconds."""

    def get(self, request):
        today = timezone.localdate()
        patients_today = Patient.objects.filter(created_at__date=today)
        measurements_today = Measurement.objects.filter(measured_at__date=today)

        by_hour = dict(
            patients_today.annotate(hour=ExtractHour("created_at"))
            .values("hour")
            .annotate(n=Count("id"))
            .values_list("hour", "n")
        )
        now_hour = timezone.localtime().hour
        first = min([7, *by_hour.keys()])
        last = max([min(now_hour, 23), 17, *by_hour.keys()])
        checkins_by_hour = [{"hour": h, "count": by_hour.get(h, 0)} for h in range(first, last + 1)]

        # Latest BP per patient today, grouped by category.
        latest_bp = {}
        for m in measurements_today.filter(systolic_bp__isnull=False, diastolic_bp__isnull=False).order_by("measured_at"):
            latest_bp[m.patient_id] = m
        counts = {c.key: 0 for c in BP_CATEGORIES}
        for m in latest_bp.values():
            counts[bp_category(m.systolic_bp, m.diastolic_bp).key] += 1
        bp_categories = [
            {"key": c.key, "label": c.label, "status": c.status, "icon": c.icon, "count": counts[c.key]}
            for c in BP_CATEGORIES
        ]

        recent_bp = list(
            Measurement.objects.filter(systolic_bp__isnull=False, diastolic_bp__isnull=False)
            .select_related("patient")
            .order_by("-measured_at")[:20]
        )
        recent_bp.reverse()

        queue = []
        tickets = (
            QueueTicket.objects.filter(is_active=True, created_at__date=today)
            .select_related("patient")
            .prefetch_related("patient__measurements")
            .order_by("created_at")[:25]
        )
        for ticket in tickets:
            vitals = latest_vitals(ticket.patient.measurements.all())
            bp, category = vitals["bp"], vitals["bp_category"]
            queue.append(
                {
                    "queue_number": ticket.queue_number,
                    "patient": ticket.patient.name,
                    "created_at": ticket.created_at.isoformat(),
                    "url": reverse("kiosk:ticket-detail", args=[ticket.qr_code_data]),
                    "weight_kg": vitals["weight"].weight_kg if vitals["weight"] else None,
                    "bp": f"{bp.systolic_bp}/{bp.diastolic_bp}" if bp else None,
                    "pulse": bp.heart_rate_bpm if bp else None,
                    "category": {"label": category.label, "status": category.status, "icon": category.icon} if category else None,
                }
            )

        return JsonResponse(
            {
                "generated_at": timezone.now().isoformat(),
                "kpis": {
                    "checkins_today": patients_today.count(),
                    "measurements_today": measurements_today.count(),
                    "waiting": len(queue),
                    "needs_attention": counts["stage2"] + counts["crisis"],
                },
                "devices": {"gateway_online": gateway_online(), "paired": len(gateway_devices())},
                "checkins_by_hour": checkins_by_hour,
                "bp_categories": bp_categories,
                "recent_bp": [
                    {
                        "t": m.measured_at.isoformat(),
                        "systolic": m.systolic_bp,
                        "diastolic": m.diastolic_bp,
                        "patient": m.patient.name,
                    }
                    for m in recent_bp
                ],
                "queue": queue,
            }
        )


class QRScannerView(LoginRequiredMixin, TemplateView):
    """QR code scanner for doctors"""

    template_name = "kiosk/qr_scanner.html"
