from django.test import TestCase
from kiosk.models import Patient, Measurement, QueueTicket


class PatientModelTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            name="John Doe",
            symptoms="Fever and headache"
        )
    
    def test_patient_creation(self):
        self.assertEqual(self.patient.name, "John Doe")
        self.assertEqual(self.patient.symptoms, "Fever and headache")
        self.assertIsNotNone(self.patient.created_at)
        self.assertTrue(self.patient.is_active)
    
    def test_patient_str(self):
        self.assertEqual(str(self.patient), "John Doe")


class MeasurementModelTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            name="Jane Doe",
            symptoms="Cough"
        )
        self.measurement = Measurement.objects.create(
            patient=self.patient,
            weight_kg=65.5,
            systolic_bp=120,
            diastolic_bp=80,
            heart_rate_bpm=72
        )
    
    def test_measurement_creation(self):
        self.assertEqual(self.measurement.weight_kg, 65.5)
        self.assertEqual(self.measurement.systolic_bp, 120)
        self.assertEqual(self.measurement.diastolic_bp, 80)
        self.assertEqual(self.measurement.heart_rate_bpm, 72)
    
    def test_measurement_patient_relationship(self):
        self.assertEqual(self.measurement.patient, self.patient)
        self.assertEqual(self.patient.measurements.count(), 1)


class QueueTicketModelTest(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            name="Test Patient",
            symptoms="Checkup"
        )
        self.ticket = QueueTicket.objects.create(
            patient=self.patient,
            queue_number="A001"
        )
    
    def test_ticket_creation(self):
        self.assertEqual(self.ticket.queue_number, "A001")
        self.assertTrue(self.ticket.is_active)
        self.assertEqual(self.ticket.status, "waiting")
        self.assertIsNotNone(self.ticket.qr_code_data)
