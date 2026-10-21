import uuid

from django.db import models

from .crypto import decrypt, encrypt


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
    SOURCE_DEVICE = "device"
    SOURCE_SIMULATED = "simulated"
    SOURCE_CHOICES = [
        (SOURCE_DEVICE, "Medical device"),
        (SOURCE_SIMULATED, "Simulated (testing only)"),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="measurements"
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_DEVICE)
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


class DeviceReading(models.Model):
    """A measurement received from a Bluetooth device via the BLE gateway.

    It belongs to no patient until the kiosk claims it, which creates the
    patient's Measurement. A reading can be claimed once.
    """

    KIND_BLOOD_PRESSURE = "bp"
    KIND_WEIGHT = "weight"
    KIND_CHOICES = [(KIND_BLOOD_PRESSURE, "Blood pressure"), (KIND_WEIGHT, "Weight")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    device_address = models.CharField(max_length=17)
    device_model = models.CharField(max_length=40)
    measured_at = models.DateTimeField(help_text="Time reported by the device")
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    systolic_bp = models.IntegerField(null=True, blank=True)
    diastolic_bp = models.IntegerField(null=True, blank=True)
    heart_rate_bpm = models.IntegerField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    measurement = models.OneToOneField(
        Measurement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="device_reading",
    )

    class Meta:
        ordering = ["-measured_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["device_address", "kind", "measured_at"], name="unique_device_reading"
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} from {self.device_model} at {self.measured_at}"


class SiteConfiguration(models.Model):
    """Singleton holding runtime settings managed from the admin.

    Secrets are stored encrypted (see kiosk.crypto) and are never shown back
    in the admin; only a masked hint is displayed.
    """

    openai_api_key_encrypted = models.TextField(blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System settings"
        verbose_name_plural = "System settings"

    def __str__(self):
        return "System settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def openai_api_key(self):
        return decrypt(self.openai_api_key_encrypted)

    @openai_api_key.setter
    def openai_api_key(self, value):
        self.openai_api_key_encrypted = encrypt(value) if value else ""

    @property
    def openai_api_key_hint(self):
        key = self.openai_api_key
        if not key:
            return ""
        return f"{key[:3]}…{key[-4:]}"


def get_openai_api_key():
    """The OpenAI API key configured in the admin, or "" if none is set."""
    return SiteConfiguration.load().openai_api_key
