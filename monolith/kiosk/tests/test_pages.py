from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from kiosk.models import Measurement, Patient, QueueTicket
from kiosk.vitals import bp_category, heart_rate_status


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
        self.patient = Patient.objects.create(name="Siti Aminah", symptoms="Dizzy since this morning")
        Measurement.objects.create(patient=self.patient, weight_kg=70.7)
        Measurement.objects.create(patient=self.patient, systolic_bp=165, diastolic_bp=95, heart_rate_bpm=88)
        self.ticket = QueueTicket.objects.create(patient=self.patient, queue_number="A001")

    def test_ticket_is_doctor_summary(self):
        page = self.client.get(reverse("kiosk:ticket-detail", args=[self.ticket.qr_code_data])).content.decode()
        for text in ["Siti Aminah", "A001", "Dizzy since this morning", "165/95", "70.7", "88", "Hypertension stage 2", "Consider seeing this patient first"]:
            self.assertIn(text, page)

    def test_patient_detail_has_chart_data(self):
        response = self.client.get(reverse("kiosk:patient-detail", args=[self.patient.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.context["chart_data"]
        self.assertEqual([p["systolic"] for p in data["bp"]], [165])
        self.assertEqual([p["weight"] for p in data["weight"]], [70.7])
        self.assertContains(response, 'id="chart-data"')

    def test_patient_list_shows_latest_vitals(self):
        response = self.client.get(reverse("kiosk:patient-list"), {"search": "siti"})
        self.assertContains(response, "165/95")
        self.assertContains(response, "Hypertension stage 2")
        self.assertNotContains(self.client.get(reverse("kiosk:patient-list"), {"search": "nobody"}), "165/95")

    def test_dashboard_data(self):
        self.assertEqual(self.client.get(reverse("kiosk:dashboard")).status_code, 200)
        data = self.client.get(reverse("kiosk:dashboard-data")).json()
        self.assertEqual(data["kpis"], {"checkins_today": 1, "measurements_today": 2, "waiting": 1, "needs_attention": 1})
        self.assertEqual(sum(r["count"] for r in data["checkins_by_hour"]), 1)
        self.assertEqual({c["key"]: c["count"] for c in data["bp_categories"]}["stage2"], 1)
        self.assertEqual(data["recent_bp"][0]["systolic"], 165)
        row = data["queue"][0]
        self.assertEqual((row["queue_number"], row["bp"], row["weight_kg"]), ("A001", "165/95", 70.7))
        self.assertEqual(row["category"]["status"], "critical")

    def test_dashboard_data_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("kiosk:dashboard-data")).status_code, 302)


class KioskPageTest(TestCase):
    def test_kiosk_page_hides_simulation_in_production(self):
        page = self.client.get(reverse("kiosk:home")).content.decode()
        self.assertIn("const SIMULATION_ENABLED = false;", page)
        self.assertNotIn("```", page)
