from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk.models import Measurement, Patient, Visit
from kiosk.vitals import bp_category, heart_rate_status
from .kiosk_helpers import as_kiosk


class BpCategoryTest(TestCase):
    def test_acc_aha_boundaries(self):
        cases = [
            ((119, 79), "normal"),
            ((120, 79), "elevated"),
            ((129, 79), "elevated"),
            ((130, 70), "stage1"),
            ((118, 80), "stage1"),
            ((140, 70), "stage2"),
            ((120, 90), "stage2"),
            ((181, 100), "crisis"),
            ((150, 121), "crisis"),
        ]
        for (systolic, diastolic), key in cases:
            self.assertEqual(bp_category(systolic, diastolic).key, key, (systolic, diastolic))
        self.assertIsNone(bp_category(None, 80))

    def test_heart_rate(self):
        self.assertEqual(heart_rate_status(72).status, "good")
        self.assertEqual(heart_rate_status(55).status, "warning")
        self.assertEqual(heart_rate_status(130).status, "critical")
        self.assertIsNone(heart_rate_status(None))


class StaffPagesTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("doctor", password="a-long-password-123")
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(name="Siti Aminah", has_drug_allergy=True, drug_allergies="penicillin")
        self.visit = Visit.objects.create(
            patient=self.patient, reason="Dizzy since this morning", queue_date=timezone.localdate(), queue_number="A001"
        )
        Measurement.objects.create(patient=self.patient, visit=self.visit, weight_kg=70.7)
        Measurement.objects.create(patient=self.patient, visit=self.visit, systolic_bp=165, diastolic_bp=95, heart_rate_bpm=88)

    def test_visit_page_is_doctor_summary(self):
        page = self.client.get(reverse("kiosk:visit-detail", args=[self.visit.pk])).content.decode()
        for text in ["Siti Aminah", self.patient.patient_id, "A001", "Dizzy since this morning", "165/95", "70.7", "88", "Hypertension stage 2", "Drug allergy:", "penicillin"]:
            self.assertIn(text, page)

    def test_qr_link_opens_visit_for_staff(self):
        response = self.client.get(reverse("kiosk:visit-token", args=[self.visit.token]))
        self.assertRedirects(response, reverse("kiosk:visit-detail", args=[self.visit.pk]))
        legacy = self.client.get(f"/ticket/{self.visit.token}/")
        self.assertRedirects(legacy, reverse("kiosk:visit-token", args=[self.visit.token]), target_status_code=302)

    def test_patient_detail_has_chart_data_and_visits(self):
        response = self.client.get(reverse("kiosk:patient-detail", args=[self.patient.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.context["chart_data"]
        self.assertEqual([p["systolic"] for p in data["bp"]], [165])
        self.assertEqual([p["weight"] for p in data["weight"]], [70.7])
        self.assertContains(response, "Dizzy since this morning")

    def test_patient_list_search(self):
        response = self.client.get(reverse("kiosk:patient-list"), {"search": "siti"})
        self.assertContains(response, "165/95")
        self.assertContains(response, "Hypertension stage 2")
        by_id = self.client.get(reverse("kiosk:patient-list"), {"search": self.patient.patient_id.lower()})
        self.assertContains(by_id, "Siti Aminah")
        self.assertNotContains(self.client.get(reverse("kiosk:patient-list"), {"search": "nobody"}), "165/95")

    def test_dashboard_data(self):
        self.assertEqual(self.client.get(reverse("kiosk:dashboard")).status_code, 200)
        data = self.client.get(reverse("kiosk:dashboard-data")).json()
        self.assertEqual(data["kpis"], {"checkins_today": 1, "measurements_today": 2, "waiting": 1, "needs_attention": 1})
        self.assertEqual(sum(r["count"] for r in data["checkins_by_hour"]), 1)
        row = data["queue"][0]
        self.assertEqual((row["queue_number"], row["bp"], row["weight_kg"], row["patient_id"]), ("A001", "165/95", 70.7, self.patient.patient_id))
        self.assertEqual(row["category"]["status"], "critical")

    def test_dashboard_data_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("kiosk:dashboard-data")).status_code, 302)


class KioskPageTest(TestCase):
    def setUp(self):
        as_kiosk(self.client)

    def test_kiosk_page_hides_simulation_in_production(self):
        page = self.client.get(reverse("kiosk:home")).content.decode()
        self.assertIn("const SIMULATION_ENABLED = false;", page)
        self.assertNotIn("```", page)
