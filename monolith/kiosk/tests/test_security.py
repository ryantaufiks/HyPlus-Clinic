import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from kiosk.models import Patient, SiteConfiguration, Visit, get_openai_api_key


class StaffPagesRequireLoginTest(TestCase):
    def setUp(self):
        patient = Patient.objects.create(name="Test Patient")
        visit = Visit.objects.create(patient=patient, reason="Fever", queue_number="A001")
        self.urls = [
            reverse("kiosk:dashboard"),
            reverse("kiosk:patient-list"),
            reverse("kiosk:patient-detail", args=[patient.pk]),
            reverse("kiosk:patient-register"),
            reverse("kiosk:patient-edit", args=[patient.pk]),
            reverse("kiosk:submissions"),
            reverse("kiosk:doctor-queue"),
            reverse("kiosk:visit-detail", args=[visit.pk]),
            reverse("kiosk:prescription-print", args=[visit.pk]),
            reverse("kiosk:qr-scanner"),
        ]

    def test_anonymous_is_redirected_to_login(self):
        for url in self.urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(reverse("login")), url)

    def test_staff_can_open_pages(self):
        user = get_user_model().objects.create_user("nurse", password="a-long-password-123")
        self.client.force_login(user)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_kiosk_home_is_public(self):
        response = self.client.get(reverse("kiosk:home"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)


class KioskApiCsrfTest(TestCase):
    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("kiosk:api-visit-start"),
            data=json.dumps({"name": "Test", "reason": "Cough"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_with_csrf_token_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("kiosk:home"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("kiosk:api-visit-start"),
            data=json.dumps({"name": "Test", "reason": "Cough"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)

    @override_settings(DEBUG=True)
    def test_unknown_visit_returns_404(self):
        response = self.client.post(
            reverse("kiosk:api-simulated-measurement", args=["00000000-0000-4000-8000-000000000000"]),
            data=json.dumps({"weight_kg": 70}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


class SiteConfigurationTest(TestCase):
    def test_key_is_encrypted_at_rest(self):
        config = SiteConfiguration.load()
        config.openai_api_key = "sk-test-1234567890abcd"
        config.save()
        stored = SiteConfiguration.objects.values_list("openai_api_key_encrypted", flat=True).get()
        self.assertNotIn("sk-test", stored)
        self.assertEqual(get_openai_api_key(), "sk-test-1234567890abcd")
        self.assertEqual(config.openai_api_key_hint, "sk-…abcd")

    def test_singleton(self):
        SiteConfiguration.load()
        SiteConfiguration().save()
        self.assertEqual(SiteConfiguration.objects.count(), 1)


class SiteConfigurationAdminTest(TestCase):
    def setUp(self):
        self.url = reverse("admin:kiosk_siteconfiguration_change", args=[1])
        SiteConfiguration.load()

    def login(self, superuser):
        User = get_user_model()
        if superuser:
            user = User.objects.create_superuser("admin", password="a-long-password-123")
        else:
            user = User.objects.create_user("nurse", password="a-long-password-123", is_staff=True)
        self.client.force_login(user)

    def test_superuser_sets_key_and_it_is_never_rendered(self):
        self.login(superuser=True)
        response = self.client.post(self.url, {"openai_api_key": "sk-secret-value-wxyz"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_openai_api_key(), "sk-secret-value-wxyz")

        page = self.client.get(self.url).content.decode()
        self.assertNotIn("sk-secret-value-wxyz", page)
        self.assertIn("sk-…wxyz", page)

    def test_blank_submit_keeps_key_and_clear_removes_it(self):
        self.login(superuser=True)
        self.client.post(self.url, {"openai_api_key": "sk-keep-me-1234"})
        self.client.post(self.url, {"openai_api_key": ""})
        self.assertEqual(get_openai_api_key(), "sk-keep-me-1234")
        self.client.post(self.url, {"clear_openai_api_key": "on"})
        self.assertEqual(get_openai_api_key(), "")

    def test_invalid_key_is_rejected(self):
        self.login(superuser=True)
        response = self.client.post(self.url, {"openai_api_key": "not-a-key"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_openai_api_key(), "")

    def test_non_superuser_staff_cannot_open_settings(self):
        self.login(superuser=False)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class HealthzTest(TestCase):
    def test_healthz(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.json(), {"status": "ok"})
