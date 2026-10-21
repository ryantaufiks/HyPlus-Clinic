from django.test import TestCase
from django.utils import timezone

from kiosk.kiosk_api import assign_queue_number
from kiosk.models import PATIENT_ID_ALPHABET, Patient, Visit


class PatientModelTest(TestCase):
    def test_patient_id_is_generated(self):
        patient = Patient.objects.create(name="Ryan Taufik")
        self.assertEqual(len(patient.patient_id), 5)
        self.assertTrue(all(c in PATIENT_ID_ALPHABET for c in patient.patient_id))
        for c in "0O1IL":
            self.assertNotIn(c, PATIENT_ID_ALPHABET)

    def test_patient_ids_are_unique(self):
        ids = {Patient.objects.create(name=f"P{i}").patient_id for i in range(50)}
        self.assertEqual(len(ids), 50)

    def test_masked_name(self):
        self.assertEqual(Patient(name="Ryan Taufik").masked_name, "R**n T****k")
        self.assertEqual(Patient(name="Al").masked_name, "Al")

    def test_age(self):
        today = timezone.localdate()
        born = today.replace(year=today.year - 30)
        self.assertEqual(Patient(name="X", date_of_birth=born).age, 30)
        self.assertIsNone(Patient(name="X").age)

    def test_allergy_terms(self):
        patient = Patient(name="X", has_drug_allergy=True, drug_allergies="Penicillin, ibuprofen;\nAspirin")
        self.assertEqual(patient.allergy_terms(), ["Penicillin", "ibuprofen", "Aspirin"])
        self.assertEqual(Patient(name="X", has_drug_allergy=False, drug_allergies="x").allergy_terms(), [])


class QueueNumberTest(TestCase):
    def test_daily_sequence(self):
        patient = Patient.objects.create(name="X")
        visits = [Visit.objects.create(patient=patient, reason="r") for _ in range(3)]
        for v in visits:
            assign_queue_number(v)
        self.assertEqual([v.queue_number for v in visits], ["A001", "A002", "A003"])
        self.assertTrue(all(v.queue_date == timezone.localdate() for v in visits))
