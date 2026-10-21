import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk.kiosk_auth import COOKIE_NAME
from kiosk.models import DeviceReading, KioskDevice, Patient, Visit

from .kiosk_helpers import as_kiosk
from .test_queue import user_with_role


class KioskAccessTest(TestCase):
    def setUp(self):
        cache.clear()
        self.visit = Visit.objects.create(patient=Patient.objects.create(name="Dewi"), reason="r")
        self.reading = DeviceReading.objects.create(kind="weight", device_address="AA", weight_kg=70, measured_at=timezone.now())

    def post(self, url, body=None):
        return self.client.post(url, json.dumps(body or {}), content_type="application/json")

    def api_calls(self):
        return [
            self.post(reverse("kiosk:api-patient-lookup"), {"patient_id": "ABCDE"}),
            self.post(reverse("kiosk:api-visit-start"), {"name": "Spam", "reason": "Spam spam"}),
            self.post(reverse("kiosk:api-online-checkin"), {"queue_number": "A001", "phone_last4": "1234"}),
            self.client.get(reverse("kiosk:api-doctors")),
            self.post(reverse("kiosk:api-device-wait"), {"kind": "weight"}),
            self.client.get(reverse("kiosk:api-device-reading-latest") + "?kind=weight"),
            self.post(reverse("kiosk:api-device-reading-claim", args=[self.reading.pk]), {"visit": str(self.visit.token)}),
        ]

    def test_the_internet_cannot_use_the_kiosk_api(self):
        for response in self.api_calls():
            self.assertEqual(response.status_code, 403, response.request["PATH_INFO"])
        self.assertEqual(Patient.objects.count(), 1)
        self.assertFalse(self.visit.measurements.exists())
        self.assertContains(self.client.get(reverse("kiosk:home")), "not set up as a kiosk")

    def test_registered_kiosk_and_kiosk_staff_can(self):
        as_kiosk(self.client)
        self.assertEqual(self.post(reverse("kiosk:api-visit-start"), {"name": "Dewi", "reason": "Cough"}).status_code, 201)
        self.client.cookies.clear()
        self.client.force_login(user_with_role("desk", "frontdesk"))
        self.assertEqual(self.post(reverse("kiosk:api-visit-start"), {"name": "Dewi", "reason": "Cough"}).status_code, 201)
        self.client.force_login(user_with_role("budi", "doctor"))  # doctors do not run the kiosk
        self.assertEqual(self.post(reverse("kiosk:api-visit-start"), {"name": "Dewi", "reason": "Cough"}).status_code, 403)

    def test_staff_register_a_screen_which_keeps_working_after_sign_out_until_revoked(self):
        self.client.force_login(user_with_role("nurse", "nurse"))
        response = self.client.post(reverse("kiosk:kiosk-register"), {"name": "Lobby kiosk"})
        cookie = response.cookies[COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        device = KioskDevice.objects.get()
        self.assertNotEqual(device.key_hash, cookie.value)  # only the hash is stored
        self.client.logout()
        self.client.cookies[COOKIE_NAME] = cookie.value
        self.assertEqual(self.post(reverse("kiosk:api-visit-start"), {"name": "Dewi", "reason": "Cough"}).status_code, 201)

        self.client.force_login(user_with_role("admin2", "admin"))
        self.client.post(reverse("kiosk:kiosk-revoke", args=[device.pk]))
        self.client.logout()
        self.client.cookies[COOKIE_NAME] = cookie.value
        self.assertEqual(self.post(reverse("kiosk:api-visit-start"), {"name": "Dewi", "reason": "Cough"}).status_code, 403)

    def test_only_device_managers_register_kiosks(self):
        self.client.force_login(user_with_role("desk", "frontdesk"))
        self.assertEqual(self.client.post(reverse("kiosk:kiosk-register"), {"name": "x"}).status_code, 403)
