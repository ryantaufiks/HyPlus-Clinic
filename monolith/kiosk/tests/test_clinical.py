import datetime as dt

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk.roles import apply_role
from kiosk.models import AuditEvent, Measurement, Patient, PatientSubmission, PrescriptionItem, Visit

PROFILE = {
    "name": "Siti Aminah",
    "id_type": "ktp",
    "id_last4": "1234",
    "phone": "+62 812 3456 7890",
    "date_of_birth": "1980-05-17",
    "height_cm": "158",
    "weight_kg": "61.5",
    "address": "Jl. Melati 5, Bandung",
    "has_drug_allergy": "yes",
    "drug_allergies": "Penicillin",
    "medical_history": "Hypertension since 2019",
}


def make_user(username, doctor=False, staff=False):
    """A front-desk user by default; doctor or nurse (staff) on request."""
    user = get_user_model().objects.create_user(username, password="a-long-password-123")
    if doctor:
        apply_role(user, "doctor")
    elif staff:
        apply_role(user, "nurse")
    return user


class RegistrationTest(TestCase):
    def setUp(self):
        self.nurse = make_user("nurse")
        self.client.force_login(self.nurse)

    def test_staff_registers_patient(self):
        response = self.client.post(reverse("kiosk:patient-register"), PROFILE)
        patient = Patient.objects.get()
        self.assertRedirects(response, reverse("kiosk:patient-detail", args=[patient.pk]))
        self.assertEqual(len(patient.patient_id), 5)
        self.assertEqual((patient.id_last4, patient.has_drug_allergy, patient.drug_allergies), ("1234", True, "Penicillin"))
        self.assertTrue(patient.is_registered)
        weight = Measurement.objects.get()
        self.assertEqual((weight.weight_kg, weight.source), (61.5, Measurement.SOURCE_MANUAL))
        self.assertEqual(AuditEvent.objects.get().action, "patient.registered")

    def test_validation(self):
        bad = {**PROFILE, "id_last4": "12", "phone": "abc", "date_of_birth": "2999-01-01", "drug_allergies": ""}
        response = self.client.post(reverse("kiosk:patient-register"), bad)
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        for field in ("id_last4", "phone", "date_of_birth", "drug_allergies"):
            self.assertIn(field, errors)
        self.assertFalse(Patient.objects.exists())

    def test_edit_records_changed_fields(self):
        patient = Patient.objects.create(name="Siti")
        self.client.post(reverse("kiosk:patient-edit", args=[patient.pk]), {**PROFILE, "weight_kg": ""})
        patient.refresh_from_db()
        self.assertEqual(patient.name, "Siti Aminah")
        event = AuditEvent.objects.get(action="patient.updated")
        self.assertIn("phone", event.detail["fields"])
        self.assertFalse(Measurement.objects.exists())


class PatientSelfServiceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.patient = Patient.objects.create(name="Siti", medical_history="SECRET HISTORY", phone="+62 811 111 111")
        self.visit = Visit.objects.create(patient=self.patient, reason="Dizzy")
        self.url = reverse("kiosk:visit-token", args=[self.visit.token])

    def test_form_never_shows_stored_data(self):
        page = self.client.get(self.url).content.decode()
        self.assertIn("Complete your registration", page)
        self.assertIn(self.patient.patient_id, page)
        self.assertNotIn("SECRET HISTORY", page)
        self.assertNotIn("+62 811 111 111", page)
        self.assertNotIn("Dizzy", page)

    def test_submission_waits_for_review(self):
        response = self.client.post(self.url, PROFILE)
        self.assertContains(response, "Thank you")
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.medical_history, "SECRET HISTORY")  # unchanged until approved
        submission = PatientSubmission.objects.get()
        self.assertEqual((submission.status, submission.data["id_last4"]), (PatientSubmission.PENDING, "1234"))

    def test_newer_submission_replaces_pending(self):
        self.client.post(self.url, PROFILE)
        self.client.post(self.url, {**PROFILE, "phone": "+62 813 0000 0000"})
        self.assertEqual(PatientSubmission.objects.filter(status=PatientSubmission.PENDING).count(), 1)

    def test_link_expires(self):
        Visit.objects.filter(pk=self.visit.pk).update(created_at=timezone.now() - dt.timedelta(days=8))
        self.assertContains(self.client.get(self.url), "This link has expired")
        self.client.post(self.url, PROFILE)
        self.assertFalse(PatientSubmission.objects.exists())

    def test_staff_approve(self):
        self.client.post(self.url, PROFILE)
        submission = PatientSubmission.objects.get()
        self.client.force_login(make_user("nurse"))
        self.assertContains(self.client.get(reverse("kiosk:submissions")), "Hypertension since 2019")
        self.client.post(reverse("kiosk:submission-review", args=[submission.pk]), {"decision": "approve"})
        self.patient.refresh_from_db()
        self.assertEqual((self.patient.name, self.patient.date_of_birth), ("Siti Aminah", dt.date(1980, 5, 17)))
        self.assertTrue(self.patient.is_registered)
        weight = Measurement.objects.get()
        self.assertEqual((weight.source, weight.visit), (Measurement.SOURCE_PATIENT, self.visit))
        submission.refresh_from_db()
        self.assertEqual(submission.status, PatientSubmission.APPROVED)

    def test_staff_reject(self):
        self.client.post(self.url, PROFILE)
        submission = PatientSubmission.objects.get()
        self.client.force_login(make_user("nurse"))
        self.client.post(reverse("kiosk:submission-review", args=[submission.pk]), {"decision": "reject", "note": "Wrong person"})
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.name, "Siti")
        submission.refresh_from_db()
        self.assertEqual((submission.status, submission.review_note), (PatientSubmission.REJECTED, "Wrong person"))


class MergeTest(TestCase):
    def test_merge_moves_records(self):
        main = Patient.objects.create(name="Ryan Taufik", phone="+62 812 1")
        duplicate = Patient.objects.create(name="Ryan", has_drug_allergy=True, drug_allergies="Aspirin")
        visit = Visit.objects.create(patient=duplicate, reason="Cough")
        Measurement.objects.create(patient=duplicate, visit=visit, weight_kg=70)

        self.client.force_login(make_user("nurse"))
        self.assertEqual(self.client.post(reverse("kiosk:patient-merge", args=[duplicate.pk]), {"target": main.patient_id}).status_code, 403)

        self.client.force_login(make_user("admin", staff=True))
        response = self.client.post(reverse("kiosk:patient-merge", args=[duplicate.pk]), {"target": main.patient_id.lower()})
        self.assertRedirects(response, reverse("kiosk:patient-detail", args=[main.pk]))
        main.refresh_from_db()
        self.assertFalse(Patient.objects.filter(pk=duplicate.pk).exists())
        self.assertEqual((main.visits.count(), main.measurements.count()), (1, 1))
        self.assertEqual((main.name, main.has_drug_allergy, main.drug_allergies), ("Ryan Taufik", True, "Aspirin"))


class DoctorTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(name="Siti", has_drug_allergy=True, drug_allergies="penicillin, ibuprofen")
        self.visit = Visit.objects.create(patient=self.patient, reason="Fever", queue_date=timezone.localdate(), queue_number="A001")
        self.url = reverse("kiosk:visit-detail", args=[self.visit.pk])

    def form(self, drugs, **extra):
        data = {
            "diagnosis": "Acute pharyngitis",
            "diagnosis_code": "j02.9",
            "doctor_notes": "",
            "prescriptions-TOTAL_FORMS": str(len(drugs)),
            "prescriptions-INITIAL_FORMS": "0",
            "prescriptions-MIN_NUM_FORMS": "0",
            "prescriptions-MAX_NUM_FORMS": "1000",
        }
        for i, drug in enumerate(drugs):
            data.update({f"prescriptions-{i}-drug": drug, f"prescriptions-{i}-dose": "500 mg", f"prescriptions-{i}-frequency": "3x daily", f"prescriptions-{i}-duration": "5 days"})
        data.update(extra)
        return data

    def test_nurse_cannot_prescribe(self):
        self.client.force_login(make_user("nurse"))
        page = self.client.get(self.url).content.decode()
        self.assertIn("Only members of the Doctor group", page)
        self.client.post(self.url, self.form(["Paracetamol"]))
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosis, "")
        self.assertFalse(PrescriptionItem.objects.exists())

    def test_doctor_records_diagnosis_and_prescription(self):
        doctor = make_user("dr", doctor=True)
        self.client.force_login(doctor)
        response = self.client.post(self.url, self.form(["Paracetamol"], complete="1"))
        self.assertRedirects(response, reverse("kiosk:doctor-queue"))
        self.visit.refresh_from_db()
        self.assertEqual((self.visit.diagnosis_code, self.visit.status, self.visit.doctor), ("J02.9", Visit.COMPLETED, doctor))
        item = PrescriptionItem.objects.get()
        self.assertEqual((item.drug, item.created_by, item.allergy_override), ("Paracetamol", doctor, False))
        self.assertEqual(AuditEvent.objects.get().action, "visit.completed")
        print_page = self.client.get(reverse("kiosk:prescription-print", args=[self.visit.pk])).content.decode()
        for text in ["Paracetamol", "500 mg", "Acute pharyngitis", "penicillin, ibuprofen"]:
            self.assertIn(text, print_page)

    def test_allergy_conflict_needs_confirmation(self):
        self.client.force_login(make_user("dr", doctor=True))
        response = self.client.post(self.url, self.form(["Ibuprofen 400"]))
        self.assertContains(response, "Allergy warning")
        self.assertFalse(PrescriptionItem.objects.exists())

        self.client.post(self.url, self.form(["Ibuprofen 400"], confirm_allergy="1"))
        item = PrescriptionItem.objects.get()
        self.assertTrue(item.allergy_override)
        self.assertEqual(AuditEvent.objects.get().detail["allergy_overrides"], ["Ibuprofen 400"])

    def test_queue_lists_critical_first(self):
        calm = Visit.objects.create(patient=Patient.objects.create(name="Calm"), reason="x", queue_date=timezone.localdate(), queue_number="A002")
        urgent = Visit.objects.create(patient=Patient.objects.create(name="Urgent"), reason="x", queue_date=timezone.localdate(), queue_number="A003")
        Measurement.objects.create(patient=urgent.patient, visit=urgent, systolic_bp=190, diastolic_bp=125)
        Measurement.objects.create(patient=calm.patient, visit=calm, systolic_bp=115, diastolic_bp=75)
        self.client.force_login(make_user("dr", doctor=True))
        rows = self.client.get(reverse("kiosk:doctor-queue")).context["waiting"]
        self.assertEqual([r["visit"].queue_number for r in rows], ["A003", "A001", "A002"])
