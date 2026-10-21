"""Bluetooth device integration.

The BLE gateway (monolith/gateway) reads OMRON devices on the server's
Bluetooth adapter and posts readings to the internal endpoints. The kiosk
page tells the server which kind of reading it is waiting for, polls for a
fresh reading, and claims it for the current patient.
"""

import datetime as dt
import hmac
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from .models import DeviceReading, Measurement, Patient

logger = logging.getLogger(__name__)

KINDS = {DeviceReading.KIND_BLOOD_PRESSURE, DeviceReading.KIND_WEIGHT}
WAIT_TTL_SECONDS = 180
GATEWAY_STATUS_TTL_SECONDS = 30
# Tolerance between the device clock (synced by the gateway) and the server.
CLOCK_TOLERANCE = dt.timedelta(minutes=2)
# The kiosk may only look back this far, so the public endpoint never exposes old readings.
MAX_LOOKBACK = dt.timedelta(minutes=15)

GATEWAY_STATUS_KEY = "gateway:status"


def _waiting_key(kind):
    return f"kiosk:waiting:{kind}"


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return None


def _reading_json(reading):
    return {
        "id": reading.id,
        "kind": reading.kind,
        "device_model": reading.device_model,
        "measured_at": reading.measured_at.isoformat(),
        "systolic_bp": reading.systolic_bp,
        "diastolic_bp": reading.diastolic_bp,
        "heart_rate_bpm": reading.heart_rate_bpm,
        "weight_kg": reading.weight_kg,
    }


def gateway_online():
    return cache.get(GATEWAY_STATUS_KEY) is not None


# --- Internal API (gateway → server) ---------------------------------------------


class GatewayAuthMixin:
    """Bearer-token auth for the BLE gateway. CSRF does not apply: no cookies are used."""

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        expected = settings.GATEWAY_TOKEN
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if not expected or not hmac.compare_digest(token, expected):
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return super().dispatch(request, *args, **kwargs)


class GatewayHeartbeatView(GatewayAuthMixin, View):
    def post(self, request):
        data = _json_body(request) or {}
        cache.set(
            GATEWAY_STATUS_KEY,
            {"at": timezone.now().isoformat(), "devices": data.get("devices", [])},
            GATEWAY_STATUS_TTL_SECONDS,
        )
        waiting = [kind for kind in sorted(KINDS) if cache.get(_waiting_key(kind))]
        return JsonResponse({"waiting": waiting})


class DeviceReadingIngestView(GatewayAuthMixin, View):
    def post(self, request):
        data = _json_body(request)
        if data is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        kind = data.get("kind")
        measured_at = parse_datetime(data.get("measured_at") or "")
        if kind not in KINDS or measured_at is None or timezone.is_naive(measured_at):
            return JsonResponse({"error": "kind and timezone-aware measured_at are required"}, status=400)

        fields = {"device_model": str(data.get("device_model", ""))[:40]}
        try:
            if kind == DeviceReading.KIND_BLOOD_PRESSURE:
                fields.update(
                    systolic_bp=int(data["systolic"]),
                    diastolic_bp=int(data["diastolic"]),
                    heart_rate_bpm=int(data["heart_rate"]) if data.get("heart_rate") is not None else None,
                )
            else:
                fields.update(weight_kg=float(data["weight_kg"]))
        except (KeyError, TypeError, ValueError):
            return JsonResponse({"error": "Missing or invalid measurement values"}, status=400)

        try:
            reading, created = DeviceReading.objects.get_or_create(
                device_address=str(data.get("device_address", "")).upper()[:17],
                kind=kind,
                measured_at=measured_at,
                defaults=fields,
            )
        except IntegrityError:
            return JsonResponse({"status": "duplicate"}, status=200)
        if created:
            logger.info("Received %s reading %s from %s", kind, reading.id, reading.device_model)
        return JsonResponse({"id": reading.id, "created": created}, status=201 if created else 200)


# --- Kiosk API (browser → server) ---------------------------------------------------

kiosk_ratelimit = ratelimit(key="ip", rate="120/m", block=True)


@method_decorator(kiosk_ratelimit, name="dispatch")
class DeviceWaitView(View):
    """The kiosk is on a measurement step: ask the gateway to poll that kind of device."""

    def post(self, request):
        data = _json_body(request) or {}
        kind = data.get("kind")
        if kind not in KINDS:
            return JsonResponse({"error": "Unknown device kind"}, status=400)
        cache.set(_waiting_key(kind), True, WAIT_TTL_SECONDS)
        return JsonResponse({"gateway_online": gateway_online()})


@method_decorator(kiosk_ratelimit, name="dispatch")
class LatestDeviceReadingView(View):
    """The newest unclaimed reading of `kind` taken since `since` (ISO 8601)."""

    def get(self, request):
        kind = request.GET.get("kind")
        since = parse_datetime(request.GET.get("since", ""))
        if kind not in KINDS or since is None or timezone.is_naive(since):
            return JsonResponse({"error": "kind and timezone-aware since are required"}, status=400)
        now = timezone.now()
        since = max(since, now - MAX_LOOKBACK)

        reading = (
            DeviceReading.objects.filter(
                kind=kind,
                measurement__isnull=True,
                measured_at__gte=since - CLOCK_TOLERANCE,
                received_at__gte=since,
            )
            .order_by("-measured_at")
            .first()
        )
        return JsonResponse(
            {
                "reading": _reading_json(reading) if reading else None,
                "gateway_online": gateway_online(),
            }
        )


@method_decorator(kiosk_ratelimit, name="dispatch")
class ClaimDeviceReadingView(View):
    """Attach a reading to the patient being checked in. A reading can be claimed once."""

    def post(self, request, pk):
        data = _json_body(request) or {}
        try:
            patient_id = int(data.get("patient_id"))
        except (TypeError, ValueError):
            return JsonResponse({"error": "patient_id is required"}, status=400)
        patient = get_object_or_404(Patient, pk=patient_id)
        with transaction.atomic():
            reading = get_object_or_404(DeviceReading.objects.select_for_update(), pk=pk)
            if reading.measurement_id is not None:
                return JsonResponse({"error": "Reading already used"}, status=409)
            if reading.received_at < timezone.now() - MAX_LOOKBACK:
                return JsonResponse({"error": "Reading expired"}, status=410)
            measurement = Measurement.objects.create(
                patient=patient,
                source=Measurement.SOURCE_DEVICE,
                systolic_bp=reading.systolic_bp,
                diastolic_bp=reading.diastolic_bp,
                heart_rate_bpm=reading.heart_rate_bpm,
                weight_kg=reading.weight_kg,
            )
            reading.measurement = measurement
            reading.save(update_fields=["measurement"])
        return JsonResponse({"measurement_id": measurement.id, "reading": _reading_json(reading)}, status=201)
