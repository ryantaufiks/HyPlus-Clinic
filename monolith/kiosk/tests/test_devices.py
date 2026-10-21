import datetime as dt
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from kiosk.models import DeviceReading, GatewayCommand, Measurement, Patient

TOKEN = "test-gateway-token"


def post_json(client, url, data, **extra):
    return client.post(url, data=json.dumps(data), content_type="application/json", **extra)


@override_settings(GATEWAY_TOKEN=TOKEN)
class GatewayApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}

    def bp_payload(self, **overrides):
        payload = {
            "device_address": "aa:bb:cc:dd:ee:ff",
            "device_model": "HEM-6232T",
            "kind": "bp",
            "measured_at": timezone.now().isoformat(),
            "systolic": 128,
            "diastolic": 84,
            "heart_rate": 71,
        }
        payload.update(overrides)
        return payload

    def test_requires_token(self):
        url = reverse("kiosk:internal-device-reading")
        self.assertEqual(post_json(self.client, url, self.bp_payload()).status_code, 401)
        bad = {"HTTP_AUTHORIZATION": "Bearer wrong"}
        self.assertEqual(post_json(self.client, url, self.bp_payload(), **bad).status_code, 401)

    def test_ingest_is_idempotent(self):
        url = reverse("kiosk:internal-device-reading")
        payload = self.bp_payload()
        self.assertEqual(post_json(self.client, url, payload, **self.auth).status_code, 201)
        self.assertEqual(post_json(self.client, url, payload, **self.auth).status_code, 200)
        reading = DeviceReading.objects.get()
        self.assertEqual((reading.systolic_bp, reading.diastolic_bp, reading.heart_rate_bpm), (128, 84, 71))
        self.assertEqual(reading.device_address, "AA:BB:CC:DD:EE:FF")

    def test_rejects_naive_timestamp_and_missing_values(self):
        url = reverse("kiosk:internal-device-reading")
        naive = self.bp_payload(measured_at="2026-10-21T10:00:00")
        self.assertEqual(post_json(self.client, url, naive, **self.auth).status_code, 400)
        missing = self.bp_payload()
        del missing["systolic"]
        self.assertEqual(post_json(self.client, url, missing, **self.auth).status_code, 400)

    def test_heartbeat_reports_waiting_kinds_and_marks_gateway_online(self):
        url = reverse("kiosk:internal-gateway-heartbeat")
        self.assertEqual(post_json(self.client, url, {}, **self.auth).json()["waiting"], [])

        wait = post_json(self.client, reverse("kiosk:api-device-wait"), {"kind": "bp"})
        self.assertTrue(wait.json()["gateway_online"])
        self.assertEqual(post_json(self.client, url, {}, **self.auth).json()["waiting"], ["bp"])


class KioskDeviceReadingTest(TestCase):
    def setUp(self):
        cache.clear()
        self.patient = Patient.objects.create(name="Test Patient", symptoms="Headache")
        self.since = timezone.now() - dt.timedelta(seconds=5)

    def make_reading(self, measured_at=None, **fields):
        defaults = {"systolic_bp": 120, "diastolic_bp": 80, "heart_rate_bpm": 70}
        defaults.update(fields)
        return DeviceReading.objects.create(
            kind="bp",
            device_address="AA:BB:CC:DD:EE:FF",
            device_model="HEM-6232T",
            measured_at=measured_at or timezone.now(),
            **defaults,
        )

    def latest(self, since=None):
        params = {"kind": "bp", "since": (since or self.since).isoformat()}
        return self.client.get(reverse("kiosk:api-device-reading-latest"), params).json()["reading"]

    def test_returns_fresh_reading_only(self):
        self.make_reading(measured_at=timezone.now() - dt.timedelta(hours=3))  # old record still in device memory
        self.assertIsNone(self.latest())
        fresh = self.make_reading()
        self.assertEqual(self.latest()["id"], fresh.id)

    def test_claim_creates_device_measurement_once(self):
        reading = self.make_reading()
        url = reverse("kiosk:api-device-reading-claim", args=[reading.id])
        response = post_json(self.client, url, {"patient_id": self.patient.id})
        self.assertEqual(response.status_code, 201)
        measurement = Measurement.objects.get()
        self.assertEqual(measurement.patient, self.patient)
        self.assertEqual(measurement.source, Measurement.SOURCE_DEVICE)
        self.assertEqual((measurement.systolic_bp, measurement.diastolic_bp), (120, 80))

        other = Patient.objects.create(name="Next Patient", symptoms="Cough")
        self.assertEqual(post_json(self.client, url, {"patient_id": other.id}).status_code, 409)
        self.assertIsNone(self.latest())

    def test_claim_requires_patient(self):
        reading = self.make_reading()
        url = reverse("kiosk:api-device-reading-claim", args=[reading.id])
        self.assertEqual(post_json(self.client, url, {}).status_code, 400)
        self.assertEqual(post_json(self.client, url, {"patient_id": 999999}).status_code, 404)

    def test_gateway_offline_without_heartbeat(self):
        params = {"kind": "bp", "since": self.since.isoformat()}
        data = self.client.get(reverse("kiosk:api-device-reading-latest"), params).json()
        self.assertFalse(data["gateway_online"])


class SimulatedMeasurementTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(name="Test Patient", symptoms="Fever")

    def post(self):
        return post_json(
            self.client,
            reverse("kiosk:api-measurement-create"),
            {"patient_id": self.patient.id, "systolic_bp": 120, "diastolic_bp": 80},
        )

    def test_disabled_in_production(self):
        self.assertEqual(self.post().status_code, 403)
        self.assertFalse(Measurement.objects.exists())

    @override_settings(DEBUG=True)
    def test_allowed_in_debug_and_marked_simulated(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(Measurement.objects.get().source, Measurement.SOURCE_SIMULATED)


@override_settings(GATEWAY_TOKEN=TOKEN)
class DeviceCommandTest(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user("nurse", password="a-long-password-123", is_staff=True)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}

    def create(self, **data):
        return post_json(self.client, reverse("kiosk:devices-command-create"), data)

    def test_staff_only(self):
        self.assertEqual(self.create(action="scan").status_code, 403)
        self.assertEqual(self.client.get(reverse("kiosk:devices")).status_code, 302)
        regular = get_user_model().objects.create_user("viewer", password="a-long-password-123")
        self.client.force_login(regular)
        self.assertEqual(self.create(action="scan").status_code, 403)
        self.assertEqual(self.client.get(reverse("kiosk:devices")).status_code, 403)

    def test_validation(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.create(action="explode").status_code, 400)
        self.assertEqual(self.create(action="pair", address="nope", model="HEM-6232T").status_code, 400)
        self.assertEqual(self.create(action="pair", address="AA:BB:CC:DD:EE:FF", model="X").status_code, 400)
        auto = self.create(action="pair", address="AA:BB:CC:DD:EE:FF")
        self.assertEqual(auto.status_code, 201)
        self.assertEqual(auto.json()["params"]["model"], "")  # gateway detects it

    def test_full_round_trip_through_gateway(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("kiosk:devices")).status_code, 200)
        created = self.create(action="pair", address="aa:bb:cc:dd:ee:ff", model="HEM-6232T")
        self.assertEqual(created.status_code, 201)
        command_id = created.json()["id"]
        self.assertEqual(created.json()["params"]["address"], "AA:BB:CC:DD:EE:FF")

        # Only one action at a time.
        self.assertEqual(self.create(action="scan").status_code, 409)

        heartbeat = post_json(self.client, reverse("kiosk:internal-gateway-heartbeat"), {}, **self.auth).json()
        self.assertEqual([c["id"] for c in heartbeat["commands"]], [command_id])
        # Handed out once.
        again = post_json(self.client, reverse("kiosk:internal-gateway-heartbeat"), {}, **self.auth).json()
        self.assertEqual(again["commands"], [])

        result_url = reverse("kiosk:internal-gateway-command-result", args=[command_id])
        post_json(self.client, result_url, {"ok": True, "result": {"model": "HEM-6232T"}}, **self.auth)
        detail = self.client.get(reverse("kiosk:devices-command-detail", args=[command_id])).json()
        self.assertEqual(detail["status"], "succeeded")
        self.assertEqual(detail["requested_by"], "nurse")

    def test_unclaimed_command_expires(self):
        self.client.force_login(self.staff)
        command_id = self.create(action="scan").json()["id"]
        GatewayCommand.objects.filter(pk=command_id).update(created_at=timezone.now() - dt.timedelta(minutes=5))
        detail = self.client.get(reverse("kiosk:devices-command-detail", args=[command_id])).json()
        self.assertEqual(detail["status"], "failed")
        self.assertIn("did not respond", detail["error"])
        self.assertEqual(self.create(action="scan").status_code, 201)
