import uuid

from django.db import models


class Patient(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    symptoms = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "is_active"]),
            models.Index(fields=["name"]),
        ]


class Measurement(models.Model):
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="measurements"
    )
    weight_kg = models.FloatField(null=True, blank=True)
    systolic_bp = models.IntegerField(null=True, blank=True)
    diastolic_bp = models.IntegerField(null=True, blank=True)
    heart_rate_bpm = models.IntegerField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    oxygen_saturation = models.IntegerField(null=True, blank=True)
    measured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Measurement for {self.patient.name} at {self.measured_at}"

    class Meta:
        ordering = ["-measured_at"]
        indexes = [
            models.Index(fields=["patient", "-measured_at"]),
        ]


class QueueTicket(models.Model):
    STATUS_CHOICES = [
        ("waiting", "Waiting"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="queue_tickets"
    )
    queue_number = models.CharField(max_length=10, unique=True, db_index=True)
    qr_code_data = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting", db_index=True)
    priority = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Queue {self.queue_number} for {self.patient.name}"

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "status", "-priority"]),
            models.Index(fields=["patient", "-created_at"]),
        ]
