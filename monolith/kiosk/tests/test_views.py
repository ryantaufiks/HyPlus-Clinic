from django.test import TestCase, Client
from django.urls import reverse
import json
from kiosk.models import Patient


class PatientAPITest(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_create_patient_success(self):
        response = self.client.post(
            reverse("kiosk:api-patient-create"),
            data=json.dumps({
                "name": "Test Patient",
                "symptoms": "Test symptoms"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Test Patient")
    
    def test_create_patient_missing_name(self):
        response = self.client.post(
            reverse("kiosk:api-patient-create"),
            data=json.dumps({
                "symptoms": "Test symptoms"
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class MeasurementAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = Patient.objects.create(
            name="Test Patient",
            symptoms="Test"
        )
    
    def test_create_measurement(self):
        response = self.client.post(
            reverse("kiosk:api-measurement-create"),
            data=json.dumps({
                "patient_id": self.patient.id,
                "weight_kg": 70.5,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate_bpm": 72
            }),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
