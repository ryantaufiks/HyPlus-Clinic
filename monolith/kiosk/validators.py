from django.core.exceptions import ValidationError
import re

def validate_patient_name(name):
    if not name or len(name.strip()) < 2:
        raise ValidationError("Name must be at least 2 characters")
    if len(name) > 100:
        raise ValidationError("Name too long")
    if not re.match(r"^[a-zA-Z\s'-]+$", name):
        raise ValidationError("Name contains invalid characters")
    return name.strip()

def validate_symptoms(symptoms):
    if not symptoms or len(symptoms.strip()) < 3:
        raise ValidationError("Symptoms must be at least 3 characters")
    return symptoms.strip()

def validate_blood_pressure(systolic, diastolic):
    if systolic and not (60 <= systolic <= 250):
        raise ValidationError("Invalid systolic BP")
    if diastolic and not (40 <= diastolic <= 150):
        raise ValidationError("Invalid diastolic BP")
    if systolic and diastolic and diastolic >= systolic:
        raise ValidationError("Diastolic must be less than systolic")

def validate_heart_rate(heart_rate):
    if heart_rate and not (30 <= heart_rate <= 220):
        raise ValidationError("Invalid heart rate")

def validate_weight(weight):
    if weight and not (20 <= weight <= 300):
        raise ValidationError("Invalid weight")
