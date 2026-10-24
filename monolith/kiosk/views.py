import datetime as dt
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import DetailView, ListView, TemplateView

from . import analytics
from .device_views import gateway_devices, gateway_online
from .kiosk_auth import kiosk_allowed
from .models import BookingRequest, Measurement, Patient, PatientSubmission, Review, Visit
from .roles import CapabilityRequiredMixin, StaffAreaMixin, can
from .vitals import bp_category, heart_rate_status

logger = logging.getLogger(__name__)

def healthz(request):
    """Readiness probe for Docker and the uptime monitor: the database and the cache must work."""
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        logger.exception("Health check: database")
        checks["database"] = "error"
    try:
        cache.set("healthz", "1", 30)
        checks["cache"] = "ok" if cache.get("healthz") == "1" else "error"
    except Exception:
        logger.exception("Health check: cache")
        checks["cache"] = "error"
    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse({"status": "ok" if healthy else "error", "checks": checks}, status=200 if healthy else 503)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(TemplateView):
    """Main kiosk interface"""

    template_name = "kiosk/home.html"

    def get_template_names(self):
        if not kiosk_allowed(self.request):
            return ["kiosk/kiosk_not_set_up.html"]
        return [self.template_name]

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
    """JSON for the Today dashboard, polled every few seconds."""

    def get(self, request):
        data = analytics.today_overview()
        user = request.user
        # Work waiting for the front desk, only what this user may act on.
        todo = []
        if can(user, "manage_bookings"):
            todo.append({"label": "Bookings to confirm", "icon": "bi-calendar2-check", "url": reverse("kiosk:bookings"),
                         "count": BookingRequest.objects.filter(status=BookingRequest.NEW).count()})
        if can(user, "review_registrations"):
            todo.append({"label": "Registrations to approve", "icon": "bi-person-plus", "url": reverse("kiosk:submissions"),
                         "count": PatientSubmission.objects.filter(status=PatientSubmission.PENDING).count()})
        if can(user, "moderate_reviews"):
            todo.append({"label": "Reviews to moderate", "icon": "bi-star", "url": reverse("kiosk:reviews"),
                         "count": Review.objects.filter(status=Review.PENDING).count()})
        data.update({
            "generated_at": timezone.now().isoformat(),
            "devices": {"gateway_online": gateway_online(), "paired": len(gateway_devices())},
            "todo": todo,
        })
        return JsonResponse(data)


class AnalyticsView(CapabilityRequiredMixin, TemplateView):
    """How the clinic did over the last 7, 30 or 90 days: for the clinic's administrators."""

    capability = "manage_staff"
    template_name = "kiosk/analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            days = int(self.request.GET.get("days", 30))
        except ValueError:
            days = 30
        days = days if days in analytics.PERIODS else 30
        report = analytics.period_report(days)
        context.update({
            "report": report, "periods": analytics.PERIODS, "days": days,
            "start": dt.date.fromisoformat(report["start"]), "end": dt.date.fromisoformat(report["end"]),
        })
        return context
