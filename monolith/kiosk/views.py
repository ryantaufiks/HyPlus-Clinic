import logging

from django.conf import settings
from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import ExtractHour
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import DetailView, ListView, TemplateView

from .device_views import gateway_devices, gateway_online
from .models import Measurement, Patient, PatientSubmission, Visit
from .roles import StaffAreaMixin
from .vitals import BP_CATEGORIES, bp_category, heart_rate_status

logger = logging.getLogger(__name__)

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
        context["title"] = "Hy+ Clinic"
        context["simulation_enabled"] = settings.DEBUG
        return context


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


def patient_search_q(query):
    query = query.strip()
    if not query:
        return Q()
    return Q(name__icontains=query) | Q(patient_id__iexact=query) | Q(phone__icontains=query)


class PatientListView(StaffAreaMixin, ListView):
    model = Patient
    template_name = "kiosk/patient_list.html"
    context_object_name = "patients"
    paginate_by = 20

    def get_queryset(self):
        search = self.request.GET.get("search", "")
        return (
            Patient.objects.filter(is_active=True)
            .filter(patient_search_q(search))
            .prefetch_related("measurements", "visits")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("search", "").strip()
        pending = set(
            PatientSubmission.objects.filter(status=PatientSubmission.PENDING).values_list("patient_id", flat=True)
        )
        context["rows"] = [
            {
                "patient": p,
                "vitals": latest_vitals(p.measurements.all()),
                "last_visit": next(iter(p.visits.all()), None),
                "pending": p.pk in pending,
            }
            for p in context["patients"]
        ]
        return context


class PatientDetailView(StaffAreaMixin, DetailView):
    model = Patient
    template_name = "kiosk/patient_detail.html"
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object
        measurements = list(patient.measurements.order_by("-measured_at"))
        context["measurements"] = measurements
        context["visits"] = patient.visits.select_related("doctor").prefetch_related("prescriptions")
        context["vitals"] = latest_vitals(measurements)
        context["pending_submission"] = patient.submissions.filter(status=PatientSubmission.PENDING).first()
        context["audit_events"] = patient.audit_events.select_related("actor")[:15]
        weight = context["vitals"]["weight"]
        if weight and patient.height_cm:
            context["bmi"] = round(weight.weight_kg / (patient.height_cm / 100) ** 2, 1)
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


class DashboardView(StaffAreaMixin, TemplateView):
    """Live overview for nurses and doctors; data comes from DashboardDataView."""

    template_name = "kiosk/dashboard.html"


class DashboardDataView(StaffAreaMixin, View):
    """JSON for the dashboard, polled every few seconds."""

    def get(self, request):
        today = timezone.localdate()
        visits_today = Visit.objects.filter(created_at__date=today)
        measurements_today = Measurement.objects.filter(measured_at__date=today)

        by_hour = dict(
            visits_today.annotate(hour=ExtractHour("created_at"))
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
        visits = (
            Visit.objects.filter(queue_date=today, status__in=[Visit.WAITING, Visit.IN_CONSULTATION])
            .exclude(queue_number="")
            .select_related("patient")
            .prefetch_related("measurements")
            .order_by("queue_number")[:25]
        )
        for visit in visits:
            vitals = latest_vitals(visit.measurements.all())
            bp, category = vitals["bp"], vitals["bp_category"]
            queue.append(
                {
                    "queue_number": visit.queue_number,
                    "patient": visit.patient.name,
                    "patient_id": visit.patient.patient_id,
                    "status": visit.get_status_display(),
                    "created_at": visit.created_at.isoformat(),
                    "url": reverse("kiosk:visit-detail", args=[visit.pk]),
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
                    "checkins_today": visits_today.count(),
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
