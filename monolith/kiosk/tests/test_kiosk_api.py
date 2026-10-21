import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from kiosk.models import Measurement, Patient, Visit
from .kiosk_helpers import as_kiosk


def post(client, url, data=None):
    return client.post(url, data=json.dumps(data or {}), content_type="application/json")


class KioskApiTest(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters
        as_kiosk(self.client)

    def test_first_visit_creates_patient_and_visit(self):
        response = post(self.client, reverse("kiosk:api-visit-start"), {"name": "  Ryan   Taufik ", "reason": "Dizzy"})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        visit = Visit.objects.get(token=data["token"])
        self.assertEqual(visit.patient.name, "Ryan Taufik")
        self.assertEqual(data["patient_id"], visit.patient.patient_id)
        self.assertFalse(data["returning"])

    def test_validation(self):
        url = reverse("kiosk:api-visit-start")
        self.assertEqual(post(self.client, url, {"name": "R", "reason": "Dizzy"}).status_code, 400)
        self.assertEqual(post(self.client, url, {"name": "Ryan", "reason": ""}).status_code, 400)
        self.assertEqual(post(self.client, url, {"patient_id": "ZZZZZ", "reason": "Dizzy"}).status_code, 404)

    def test_returning_patient(self):
        patient = Patient.objects.create(name="Ryan Taufik")
        lookup = post(self.client, reverse("kiosk:api-patient-lookup"), {"patient_id": f" {patient.patient_id.lower()} "})
        self.assertEqual(lookup.json(), {"patient_id": patient.patient_id, "masked_name": "R**n T****k"})

        response = post(self.client, reverse("kiosk:api-visit-start"), {"patient_id": patient.patient_id, "reason": "Follow-up"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Patient.objects.count(), 1)
        self.assertEqual(patient.visits.count(), 1)

    def test_lookup_unknown_and_rate_limited(self):
        url = reverse("kiosk:api-patient-lookup")
        self.assertEqual(post(self.client, url, {"patient_id": "ABCDE"}).status_code, 404)
        self.assertEqual(post(self.client, url, {"patient_id": "0000O"}).status_code, 404)
        statuses = [post(self.client, url, {"patient_id": "ABCDE"}).status_code for _ in range(12)]
        self.assertIn(403, statuses)  # guessing IDs is throttled

    @override_settings(PUBLIC_BASE_URL="https://aivin.example.org")
    def test_finish_gives_queue_number_and_qr_link(self):
        token = post(self.client, reverse("kiosk:api-visit-start"), {"name": "Ryan", "reason": "Dizzy"}).json()["token"]
        url = reverse("kiosk:api-visit-finish", args=[token])
        first = post(self.client, url).json()
        self.assertEqual(first["queue_number"], "A001")
        self.assertEqual(first["url"], f"https://aivin.example.org/v/{token}/")
        self.assertTrue(first["qr_code_image"].startswith("data:image/png;base64,"))
        self.assertEqual(post(self.client, url).json()["queue_number"], "A001")  # idempotent

    def test_simulated_measurement_is_debug_only(self):
        token = post(self.client, reverse("kiosk:api-visit-start"), {"name": "Ryan", "reason": "Dizzy"}).json()["token"]
        url = reverse("kiosk:api-simulated-measurement", args=[token])
        self.assertEqual(post(self.client, url, {"weight_kg": 70}).status_code, 403)
        with self.settings(DEBUG=True):
            self.assertEqual(post(self.client, url, {"weight_kg": 70}).status_code, 201)
        m = Measurement.objects.get()
        self.assertEqual((m.source, m.visit.token.hex), (Measurement.SOURCE_SIMULATED, token.replace("-", "")))
