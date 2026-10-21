"""Public JSON API used by the kiosk page.

The kiosk works with a visit's unguessable token, never with database ids, so
nobody can attach readings to, or read from, someone else's visit.
"""

import base64
import io
import json
import logging

import qrcode
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from . import queue
from .models import PATIENT_ID_ALPHABET, PATIENT_ID_LENGTH, Measurement, Patient, StaffProfile, Visit

logger = logging.getLogger(__name__)

kiosk_post_ratelimit = method_decorator(
    ratelimit(key="ip", rate=settings.KIOSK_API_RATE, method="POST", block=True), name="post"
)
# Patient-ID lookups are rate-limited harder to make guessing IDs impractical.
lookup_ratelimit = method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return None


def normalise_patient_id(value):
    return "".join(str(value or "").split()).upper()


def _visit_json(visit):
    return {
        "token": str(visit.token),
        "patient_id": visit.patient.patient_id,
        "first_name": visit.patient.name.split()[0] if visit.patient.name else "",
        "returning": visit.patient.visits.count() > 1,
        "doctor": visit.requested_doctor.get_full_name() or visit.requested_doctor.get_username() if visit.requested_doctor else "",
        "room": StaffProfile.room_for(visit.requested_doctor) if visit.requested_doctor else "",
    }


@lookup_ratelimit
class PatientLookupView(View):
    """Confirm a returning patient's ID; only a masked name is revealed."""

    def post(self, request):
        data = _body(request) or {}
        patient_id = normalise_patient_id(data.get("patient_id"))
        valid = len(patient_id) == PATIENT_ID_LENGTH and all(c in PATIENT_ID_ALPHABET for c in patient_id)
        patient = Patient.objects.filter(patient_id=patient_id, is_active=True).first() if valid else None
        if patient is None:
            return JsonResponse({"error": "We could not find that Patient ID. Please check it or ask a nurse."}, status=404)
        return JsonResponse({"patient_id": patient.patient_id, "masked_name": patient.masked_name})


class DoctorChoiceView(View):
    """Doctors the patient can choose at the kiosk, with how many are waiting for each."""

    def get(self, request):
        from .queue_views import _doctor_face, _doctor_name

        doctors = queue.doctors_on_duty()
        on_duty = {d.pk for d, _ in doctors}
        waiting = queue.waiting_in_order()
        shared = sum(1 for v in waiting if queue.chosen_doctor(v, on_duty) is None)
        return JsonResponse(
            {
                "doctors": [
                    {
                        "id": doctor.pk,
                        "name": _doctor_name(doctor),
                        "room": room,
                        "face": _doctor_face(doctor),
                        "waiting": sum(1 for v in waiting if v.requested_doctor_id == doctor.pk),
                    }
                    for doctor, room in doctors
                ],
                "any_waiting": shared,
            }
        )


@kiosk_post_ratelimit
class VisitStartView(View):
    """Start a visit: for a new patient (name) or a returning one (patient_id)."""

    def post(self, request):
        data = _body(request)
        if data is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        reason = " ".join(str(data.get("reason", "")).split())
        if len(reason) < 3:
            return JsonResponse({"error": "Please tell us the reason for your visit."}, status=400)

        if data.get("patient_id"):
            patient = Patient.objects.filter(
                patient_id=normalise_patient_id(data["patient_id"]), is_active=True
            ).first()
            if patient is None:
                return JsonResponse({"error": "Unknown Patient ID"}, status=404)
        else:
            name = " ".join(str(data.get("name", "")).split())
            if len(name) < 2 or len(name) > 100:
                return JsonResponse({"error": "Please enter your full name."}, status=400)
            patient = Patient.objects.create(name=name)

        doctor = None
        if data.get("doctor_id"):
            doctor = next((d for d, _ in queue.doctors_on_duty() if str(d.pk) == str(data["doctor_id"])), None)
            if doctor is None:
                return JsonResponse({"error": "That doctor is no longer available. Please choose again."}, status=409)

        visit = Visit.objects.create(patient=patient, reason=reason[:2000], requested_doctor=doctor)
        return JsonResponse(_visit_json(visit), status=201)


@kiosk_post_ratelimit
class VisitFinishView(View):
    """Give the visit its queue number and the QR code for the ticket."""

    def post(self, request, token):
        visit = get_object_or_404(Visit.objects.select_related("patient"), token=token)
        if not visit.queue_number:
            assign_queue_number(visit)

        path = reverse("kiosk:visit-token", args=[visit.token])
        # The QR is scanned by phones, so it must use the public address even
        # when the kiosk itself is opened on localhost.
        url = settings.PUBLIC_BASE_URL + path if settings.PUBLIC_BASE_URL else request.build_absolute_uri(path)
        image = qrcode.make(url, box_size=8, border=2)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return JsonResponse(
            {
                **_visit_json(visit),
                "queue_number": visit.queue_number,
                "url": url,
                "qr_code_image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
            }
        )


def assign_queue_number(visit):
    """Next daily queue number (A001, A002, … reset every day)."""
    today = timezone.localdate()
    for _ in range(5):
        taken = Visit.objects.filter(queue_date=today).exclude(queue_number="").count()
        visit.queue_date = today
        visit.queue_number = f"A{taken + 1:03d}"
        try:
            with transaction.atomic():
                visit.save(update_fields=["queue_date", "queue_number"])
            return
        except IntegrityError:
            continue  # another kiosk took the number at the same moment
    raise RuntimeError("Could not assign a queue number")


@kiosk_post_ratelimit
class SimulatedMeasurementView(View):
    """Record a simulated measurement. Only available with DEBUG on.

    Real measurements come from medical devices through the BLE gateway and
    are claimed via the device-reading API, never typed in by the kiosk.
    """

    def post(self, request, token):
        if not settings.DEBUG:
            return JsonResponse({"error": "Simulated measurements are disabled"}, status=403)
        visit = get_object_or_404(Visit, token=token)
        data = _body(request) or {}
        try:
            values = {
                key: (float(data[key]) if key == "weight_kg" else int(data[key]))
                for key in ("weight_kg", "systolic_bp", "diastolic_bp", "heart_rate_bpm")
                if data.get(key) is not None
            }
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid values"}, status=400)
        measurement = Measurement.objects.create(
            patient=visit.patient, visit=visit, source=Measurement.SOURCE_SIMULATED, **values
        )
        return JsonResponse({"id": measurement.id, "measured_at": measurement.measured_at.isoformat()}, status=201)
