import datetime as dt
import io
import json
import urllib.error
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import ai
from kiosk.models import AuditEvent, Measurement, Patient, PrescriptionItem, SiteConfiguration, Visit

from .test_queue import user_with_role


def openai_reply(text="Presenting complaint:\n- Cough for 5 days", model="gpt-4o-mini-2024-07-18"):
    body = json.dumps({"model": model, "choices": [{"message": {"content": text}}]}).encode()
    response = mock.MagicMock()
    response.__enter__.return_value = io.BytesIO(body)
    return response


class AISummaryTest(TestCase):
    def setUp(self):
        cache.clear()
        config = SiteConfiguration.load()
        config.openai_api_key = "sk-test-key-123456"
        config.save()
        self.doctor = user_with_role("budi", "doctor", room="Room 1")
        self.patient = Patient.objects.create(
            name="Dewi Lestari", phone="0812 3456 7890", address="Jl. Merdeka 10", id_type="ktp", id_last4="4321",
            date_of_birth=dt.date(1980, 5, 1), height_cm=160, has_drug_allergy=True, drug_allergies="Penicillin",
            medical_history="Asthma. Contact Dewi at dewi@example.com or 0812-3456-7890.",
        )
        old = Visit.objects.create(patient=self.patient, reason="Fever", status=Visit.COMPLETED, diagnosis="Pharyngitis", diagnosis_code="J02.9")
        Visit.objects.filter(pk=old.pk).update(created_at=timezone.now() - dt.timedelta(days=30))
        PrescriptionItem.objects.create(visit=old, drug="Azithromycin", dose="500 mg", frequency="1x daily")
        self.visit = Visit.objects.create(patient=self.patient, reason="Dewi has a cough for 5 days", queue_date=timezone.localdate(), queue_number="A001")
        Measurement.objects.create(patient=self.patient, visit=self.visit, systolic_bp=150, diastolic_bp=95, heart_rate_bpm=88, weight_kg=64)
        self.url = reverse("kiosk:visit-ai-summary", args=[self.visit.pk])

    def test_prompt_is_de_identified_but_clinically_complete(self):
        text = ai.summary_input(self.visit)
        for secret in ["Dewi", "Lestari", self.patient.patient_id, "0812", "Merdeka", "4321", "dewi@example.com", "1980"]:
            self.assertNotIn(secret, text)
        for fact in ["Age:", "cough for 5 days", "150/95 mmHg (Hypertension stage 2", "pulse 88", "BMI 25.0", "Penicillin", "Asthma", "Pharyngitis (J02.9)", "Azithromycin 500 mg"]:
            self.assertIn(fact, text)

    @mock.patch("kiosk.ai.urllib.request.urlopen")
    def test_doctor_generates_and_sees_summary(self, urlopen):
        urlopen.return_value = openai_reply()
        self.client.force_login(self.doctor)
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("kiosk:visit-detail", args=[self.visit.pk]) + "#ai-summary", fetch_redirect_response=False)
        request = urlopen.call_args[0][0]
        self.assertEqual(request.headers["Authorization"], "Bearer sk-test-key-123456")
        self.assertNotIn(b"Lestari", request.data)
        self.visit.refresh_from_db()
        self.assertEqual((self.visit.ai_summary_model, self.visit.ai_summary_by), ("gpt-4o-mini-2024-07-18", self.doctor))
        page = self.client.get(reverse("kiosk:visit-detail", args=[self.visit.pk]))
        self.assertContains(page, "Cough for 5 days")
        self.assertContains(page, "Review before use")
        self.assertTrue(AuditEvent.objects.filter(action="visit.ai_summary", visit=self.visit).exists())

    @mock.patch("kiosk.ai.urllib.request.urlopen")
    def test_api_errors_are_explained(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(ai.API_URL, 401, "Unauthorized", {}, None)
        self.client.force_login(self.doctor)
        page = self.client.post(self.url, follow=True)
        self.assertContains(page, "API key was rejected")
        urlopen.side_effect = TimeoutError()
        self.assertContains(self.client.post(self.url, follow=True), "Could not reach OpenAI")
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.ai_summary, "")

    def test_without_key_explains_setup(self):
        config = SiteConfiguration.load()
        config.openai_api_key = ""
        config.save()
        self.client.force_login(self.doctor)
        self.assertContains(self.client.get(reverse("kiosk:visit-detail", args=[self.visit.pk])), "Not set up yet")
        self.assertContains(self.client.post(self.url, follow=True), "No OpenAI API key is set")

    def test_only_doctors_can_generate(self):
        self.client.force_login(user_with_role("nurse", "nurse"))
        self.assertEqual(self.client.post(self.url).status_code, 403)


class AISummaryFormatTest(TestCase):
    def test_headings_lists_and_escaping(self):
        from kiosk.templatetags.ai_format import ai_summary

        html = ai_summary("Vitals today:\n- BP <b>150</b>/95\nPoints to check:\n- Recheck BP")
        self.assertEqual(html, "<h3>Vitals today</h3><ul><li>BP &lt;b&gt;150&lt;/b&gt;/95</li></ul><h3>Points to check</h3><ul><li>Recheck BP</li></ul>")
