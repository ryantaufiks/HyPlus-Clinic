from django.test import TestCase
from django.core.exceptions import ValidationError
from kiosk.validators import (
    validate_patient_name,
    validate_symptoms,
    validate_blood_pressure,
    validate_heart_rate,
    validate_weight
)


class ValidatorsTest(TestCase):
    def test_validate_patient_name_success(self):
        name = validate_patient_name("John Doe")
        self.assertEqual(name, "John Doe")
    
    def test_validate_patient_name_too_short(self):
        with self.assertRaises(ValidationError):
            validate_patient_name("A")
    
    def test_validate_symptoms_success(self):
        symptoms = validate_symptoms("Fever and cough")
        self.assertEqual(symptoms, "Fever and cough")
    
    def test_validate_blood_pressure_success(self):
        try:
            validate_blood_pressure(120, 80)
        except ValidationError:
            self.fail("validate_blood_pressure raised ValidationError unexpectedly")
    
    def test_validate_blood_pressure_invalid(self):
        with self.assertRaises(ValidationError):
            validate_blood_pressure(80, 120)  # Diastolic > Systolic
    
    def test_validate_heart_rate_success(self):
        try:
            validate_heart_rate(72)
        except ValidationError:
            self.fail("validate_heart_rate raised ValidationError unexpectedly")
    
    def test_validate_weight_success(self):
        try:
            validate_weight(70.5)
        except ValidationError:
            self.fail("validate_weight raised ValidationError unexpectedly")
