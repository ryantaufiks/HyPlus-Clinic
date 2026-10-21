"""Waiting-room TV, calling patients, and access control at the consulting room."""

import io
import json

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from . import queue
from .models import Visit
from .roles import CapabilityRequiredMixin, is_doctor


def _doctor_name(user):
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


# --- Waiting-room TV (public: queue numbers and rooms only, never patient names) --------


class DisplayView(TemplateView):
    template_name = "kiosk/display.html"


@method_decorator(never_cache, name="dispatch")
class DisplayDataView(View):
    def get(self, request):
        today = queue.todays_queue().select_related("doctor")
        called = today.filter(status=Visit.CALLED).order_by("-called_at")
        in_progress = today.filter(status=Visit.IN_CONSULTATION).order_by("room")
        return JsonResponse(
            {
                "now": timezone.now().isoformat(),
                "called": [
                    {
                        "queue_number": v.queue_number,
                        "room": v.room,
                        "doctor": _doctor_name(v.doctor),
                        "called_at": v.called_at.isoformat(),
                        "call_id": f"{v.pk}-{v.call_count}",
                    }
                    for v in called
                ],
                "in_progress": [
                    {"queue_number": v.queue_number, "room": v.room, "doctor": _doctor_name(v.doctor)} for v in in_progress
                ],
                "rooms": _rooms(called, in_progress),
                "waiting": [v.queue_number for v in queue.waiting_in_order()],
            }
        )


def _rooms(called, in_progress):
    """One row per on-duty doctor (even when free), plus any other room with a patient."""
    active = {}
    for visit in list(called) + list(in_progress):  # in progress wins over called
        active[visit.doctor_id] = visit
    rows, shown = [], set()
    for doctor, room in queue.doctors_on_duty():
        visit = active.get(doctor.pk)
        rows.append(_room_row(room, doctor, visit))
        shown.add(doctor.pk)
    for doctor_id, visit in active.items():
        if doctor_id not in shown:
            rows.append(_room_row(visit.room, visit.doctor, visit))
    return rows


def _room_row(room, doctor, visit):
    state = "available"
    if visit is not None:
        state = "in_progress" if visit.status == Visit.IN_CONSULTATION else "called"
    return {
        "room": room,
        "doctor": _doctor_name(doctor),
        "state": state,
        "queue_number": visit.queue_number if visit else "",
    }


# --- Calling patients (doctors) --------------------------------------------------------


class DoctorActionMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_doctor(self.request.user)

    def back(self, request, visit=None):
        if request.POST.get("next") == "queue" or visit is None:
            return redirect("kiosk:doctor-queue")
        return redirect("kiosk:visit-detail", visit.pk)


class DutyView(DoctorActionMixin, View):
    """A doctor marks themselves on or off duty (shown on the TV)."""

    def post(self, request):
        on_duty = request.POST.get("on_duty") == "1"
        queue.set_on_duty(request.user, on_duty)
        messages.info(request, "You are on duty." if on_duty else "You are off duty and no longer shown on the TV.")
        return redirect("kiosk:doctor-queue")


class CallNextView(DoctorActionMixin, View):
    def post(self, request):
        visit = queue.call_next(request.user)
        if visit:
            messages.success(request, f"Called {visit.queue_number} to {visit.room}.")
        else:
            messages.info(request, "Nobody is waiting.")
        return redirect("kiosk:doctor-queue")


class CallView(DoctorActionMixin, View):
    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk)
        try:
            visit = queue.call(visit, request.user)
            messages.success(request, f"Called {visit.queue_number} to {visit.room}.")
        except queue.QueueError as exc:
            messages.error(request, str(exc))
        return self.back(request, visit)


class CancelVisitView(CapabilityRequiredMixin, View):
    """Cancel a queued visit with a reason (doctors, nurses, administrators)."""

    capability = "cancel_visits"

    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk)
        try:
            visit = queue.cancel(visit, request.user, request.POST.get("reason"))
            messages.info(request, f"{visit.queue_number or 'Visit'} cancelled: {visit.cancel_reason}")
        except queue.QueueError as exc:
            messages.error(request, str(exc))
        if request.POST.get("next") == "visit":
            return redirect("kiosk:visit-detail", visit.pk)
        return redirect("kiosk:doctor-queue")


# --- Access control at the consulting-room door ----------------------------------------


class AccessControlView(CapabilityRequiredMixin, TemplateView):
    capability = "scan_tickets"
    template_name = "kiosk/access_control.html"


@method_decorator(ratelimit(key="user", rate="60/m", method="POST", block=True), name="post")
class AdmitView(CapabilityRequiredMixin, View):
    capability = "scan_tickets"

    def handle_no_permission(self):
        return JsonResponse({"ok": False, "message": "Staff login required."}, status=403)

    def post(self, request):
        try:
            token = str(json.loads(request.body or b"{}").get("token", ""))
            visit = queue.admit(token, request.user)
        except queue.QueueError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return JsonResponse({"ok": False, "message": "This is not an AIVIN ticket."}, status=400)
        return JsonResponse(
            {
                "ok": True,
                "queue_number": visit.queue_number,
                "room": visit.room,
                "doctor": _doctor_name(visit.doctor),
                "visit_url": reverse("kiosk:visit-detail", args=[visit.pk]),
            }
        )


# --- Patient's phone: live status and the ticket QR -----------------------------------


@method_decorator(never_cache, name="dispatch")
class VisitStatusView(View):
    """Public, by ticket token: queue number and progress only."""

    def get(self, request, token):
        visit = get_object_or_404(Visit, token=token)
        return JsonResponse(
            {
                "queue_number": visit.queue_number,
                "status": visit.status,
                "status_label": visit.get_status_display(),
                "room": visit.room,
                "ahead": queue.position(visit),
                "today": visit.queue_date == timezone.localdate(),
            }
        )


def ticket_qr_png(request, token):
    """The ticket QR as a PNG the patient can save to their phone."""
    visit = get_object_or_404(Visit, token=token)
    path = reverse("kiosk:visit-token", args=[visit.token])
    url = settings.PUBLIC_BASE_URL + path if settings.PUBLIC_BASE_URL else request.build_absolute_uri(path)
    buffer = io.BytesIO()
    qrcode.make(url, box_size=10, border=3).save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="aivin-ticket-{visit.queue_number or "visit"}.png"'
    return response
