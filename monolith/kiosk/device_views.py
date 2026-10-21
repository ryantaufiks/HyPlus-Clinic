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
import re

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from .models import DeviceReading, GatewayCommand, Measurement, Patient

logger = logging.getLogger(__name__)

KINDS = {DeviceReading.KIND_BLOOD_PRESSURE, DeviceReading.KIND_WEIGHT}
WAIT_TTL_SECONDS = 180
GATEWAY_STATUS_TTL_SECONDS = 30
# Tolerance between the device clock (synced by the gateway) and the server.
CLOCK_TOLERANCE = dt.timedelta(minutes=2)
# How far a device clock may lag before its readings are no longer trusted
# at all (see LatestDeviceReadingView).
MAX_CLOCK_LAG = dt.timedelta(hours=6)
# The kiosk may only look back this far, so the public endpoint never exposes old readings.
MAX_LOOKBACK = dt.timedelta(minutes=15)

GATEWAY_STATUS_KEY = "gateway:status"

SUPPORTED_MODELS = {"HEM-6232T": "Blood pressure monitor (wrist)", "HN-300T2": "Weight scale"}
ADDRESS_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
# A command the gateway has not picked up by then is failed, as is one that runs too long.
COMMAND_PICKUP_TIMEOUT = dt.timedelta(seconds=30)
COMMAND_RUN_TIMEOUT = dt.timedelta(minutes=4)


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


def gateway_devices():
    """Paired devices as last reported by the gateway (empty when it is offline)."""
    return (cache.get(GATEWAY_STATUS_KEY) or {}).get("devices", [])


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
        with transaction.atomic():
            pending = list(
                GatewayCommand.objects.select_for_update(skip_locked=True)
                .filter(status=GatewayCommand.PENDING)
                .order_by("created_at")
            )
            now = timezone.now()
            for command in pending:
                command.status = GatewayCommand.RUNNING
                command.started_at = now
                command.save(update_fields=["status", "started_at"])
        commands = [{"id": c.id, "action": c.action, "params": c.params} for c in pending]
        return JsonResponse({"waiting": waiting, "commands": commands})


class GatewayCommandResultView(GatewayAuthMixin, View):
    def post(self, request, pk):
        data = _json_body(request)
        if data is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        command = get_object_or_404(GatewayCommand, pk=pk, status=GatewayCommand.RUNNING)
        command.status = GatewayCommand.SUCCEEDED if data.get("ok") else GatewayCommand.FAILED
        command.result = data.get("result")
        command.error = str(data.get("error") or "")[:2000]
        command.finished_at = timezone.now()
        command.save(update_fields=["status", "result", "error", "finished_at"])
        return JsonResponse({"status": command.status})


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
        if data.get("waiting", True):
            cache.set(_waiting_key(kind), True, WAIT_TTL_SECONDS)
        else:
            # The kiosk left the step: stop polling the device (saves its battery).
            cache.delete(_waiting_key(kind))
        return JsonResponse({"gateway_online": gateway_online()})


@method_decorator(kiosk_ratelimit, name="dispatch")
class LatestDeviceReadingView(View):
    """The newest unclaimed reading of `kind` taken since `since` (ISO 8601).

    A reading counts as taken during this step when the server first received
    it after the step started, and either
    - its device timestamp is after the step started (device clock correct), or
    - it is newer than every reading that device had sent before the step
      started (device clock wrong: some OMRON monitors drift and do not
      always accept the gateway's clock sync). This needs at least one such
      earlier reading.
    Records still in the device's memory from earlier patients fail both.
    """

    def get(self, request):
        kind = request.GET.get("kind")
        since = parse_datetime(request.GET.get("since", ""))
        if kind not in KINDS or since is None or timezone.is_naive(since):
            return JsonResponse({"error": "kind and timezone-aware since are required"}, status=400)
        now = timezone.now()
        since = max(since, now - MAX_LOOKBACK)
        return JsonResponse(
            {
                "reading": _reading_json(reading) if (reading := fresh_reading(kind, since)) else None,
                "gateway_online": gateway_online(),
            }
        )


def fresh_reading(kind, since):
    """The reading of `kind` taken after `since`; see LatestDeviceReadingView."""
    candidates = DeviceReading.objects.filter(
        kind=kind,
        measurement__isnull=True,
        received_at__gte=since,
        measured_at__gte=since - MAX_CLOCK_LAG,
    ).order_by("-measured_at")

    on_time = candidates.filter(measured_at__gte=since - CLOCK_TOLERANCE).first()
    if on_time:
        return on_time

    for reading in candidates:
        newest_before = (
            DeviceReading.objects.filter(
                device_address=reading.device_address, kind=kind, received_at__lt=since
            )
            .order_by("-measured_at")
            .values_list("measured_at", flat=True)
            .first()
        )
        # Without an earlier reading to compare with, an old record could pass
        # as new; the gateway's polls and Test connection provide one.
        if newest_before is not None and reading.measured_at > newest_before:
            logger.warning(
                "%s clock is about %d min behind: accepting reading %s measured at %s",
                reading.device_model,
                (since - reading.measured_at).total_seconds() // 60,
                reading.id,
                reading.measured_at.isoformat(),
            )
            return reading
        break  # older candidates are older still
    return None


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


# --- Staff device management ---------------------------------------------------------


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class StaffJsonMixin(StaffRequiredMixin):
    def handle_no_permission(self):
        return JsonResponse({"error": "Staff login required"}, status=403)


def _command_json(command):
    _expire_if_stale(command)
    return {
        "id": command.id,
        "action": command.action,
        "params": command.params,
        "status": command.status,
        "result": command.result,
        "error": command.error,
        "created_at": command.created_at.isoformat(),
        "finished_at": command.finished_at.isoformat() if command.finished_at else None,
        "requested_by": command.requested_by.get_username() if command.requested_by else None,
    }


def _expire_if_stale(command):
    now = timezone.now()
    if command.status == GatewayCommand.PENDING and command.created_at < now - COMMAND_PICKUP_TIMEOUT:
        error = "The device service did not respond. Check that the gateway is running (make gateway-logs)."
    elif command.status == GatewayCommand.RUNNING and command.started_at < now - COMMAND_RUN_TIMEOUT:
        error = "Timed out waiting for the device service."
    else:
        return
    command.status = GatewayCommand.FAILED
    command.error = error
    command.finished_at = now
    command.save(update_fields=["status", "error", "finished_at"])


class DevicesPageView(StaffRequiredMixin, TemplateView):
    template_name = "kiosk/devices.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["supported_models"] = SUPPORTED_MODELS
        return context


class DeviceStatusView(StaffJsonMixin, View):
    def get(self, request):
        status = cache.get(GATEWAY_STATUS_KEY)
        devices = []
        for device in (status or {}).get("devices", []):
            latest = (
                DeviceReading.objects.filter(device_address=str(device.get("address", "")).upper())
                .order_by("-received_at")
                .first()
            )
            devices.append({**device, "latest_reading": _reading_json(latest) if latest else None})
        recent = GatewayCommand.objects.select_related("requested_by")[:10]
        return JsonResponse(
            {
                "gateway_online": status is not None,
                "gateway_seen_at": status["at"] if status else None,
                "devices": devices,
                "recent_commands": [_command_json(c) for c in recent],
            }
        )


@method_decorator(ratelimit(key="user", rate="30/m", method="POST", block=True), name="post")
class DeviceCommandCreateView(StaffJsonMixin, View):
    def post(self, request):
        data = _json_body(request) or {}
        action = data.get("action")
        params = {}
        if action == GatewayCommand.SCAN:
            params["seconds"] = 10
        elif action in (GatewayCommand.PAIR, GatewayCommand.TEST, GatewayCommand.REMOVE):
            address = str(data.get("address", "")).strip().upper()
            if not ADDRESS_RE.match(address):
                return JsonResponse({"error": "Invalid device address"}, status=400)
            params["address"] = address
            if action == GatewayCommand.PAIR:
                # Empty means auto-detect: the gateway reads the model from the device.
                model = data.get("model") or ""
                if model and model not in SUPPORTED_MODELS:
                    return JsonResponse({"error": "Choose a supported model"}, status=400)
                params["model"] = model
        else:
            return JsonResponse({"error": "Unknown action"}, status=400)

        # One action at a time: the gateway has a single Bluetooth adapter.
        active = GatewayCommand.objects.filter(status__in=[GatewayCommand.PENDING, GatewayCommand.RUNNING])
        for command in active:
            _expire_if_stale(command)
        if active.exists():
            return JsonResponse({"error": "Another device action is still running. Please wait."}, status=409)

        command = GatewayCommand.objects.create(action=action, params=params, requested_by=request.user)
        return JsonResponse(_command_json(command), status=201)


class DeviceCommandDetailView(StaffJsonMixin, View):
    def get(self, request, pk):
        command = get_object_or_404(GatewayCommand.objects.select_related("requested_by"), pk=pk)
        return JsonResponse(_command_json(command))
