import re
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .crypto import decrypt, encrypt


# Patient IDs avoid look-alike characters (0/O, 1/I/L) so they can be read
# out and typed reliably.
PATIENT_ID_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
PATIENT_ID_LENGTH = 5


def generate_patient_id():
    return "".join(secrets.choice(PATIENT_ID_ALPHABET) for _ in range(PATIENT_ID_LENGTH))


class Patient(models.Model):
    ID_TYPE_CHOICES = [
        ("ktp", "KTP"),
        ("ic", "IC"),
        ("passport", "Passport"),
        ("other", "Other"),
    ]

    # Short public identifier, printed on the kiosk ticket. It identifies a
    # record; it never grants access to one.
    patient_id = models.CharField("Patient ID", max_length=PATIENT_ID_LENGTH, unique=True, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    id_type = models.CharField("ID type", max_length=10, choices=ID_TYPE_CHOICES, blank=True)
    # Only the last four characters of the identity document are stored.
    id_last4 = models.CharField("ID number (last 4)", max_length=4, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    height_cm = models.FloatField("Height (cm)", null=True, blank=True)
    address = models.TextField(blank=True)
    has_drug_allergy = models.BooleanField("Drug allergy", null=True, blank=True)
    drug_allergies = models.TextField("Allergic to", blank=True)
    medical_history = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.patient_id})"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "is_active"]),
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = self._unused_patient_id()
        super().save(*args, **kwargs)

    @classmethod
    def _unused_patient_id(cls):
        while True:
            candidate = generate_patient_id()
            if not cls.objects.filter(patient_id=candidate).exists():
                return candidate

    @property
    def masked_name(self):
        """'Ryan Taufik' -> 'R**n T****k', for confirming identity on the public kiosk."""
        def mask(word):
            return word if len(word) <= 2 else word[0] + "*" * (len(word) - 2) + word[-1]
        return " ".join(mask(w) for w in self.name.split())

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_registered(self):
        """Whether the registration details were completed (by staff or approved)."""
        return bool(self.date_of_birth and self.phone and self.has_drug_allergy is not None)

    def allergy_terms(self):
        if not self.has_drug_allergy:
            return []
        return [t.strip() for t in re.split(r"[,;\n]+", self.drug_allergies) if len(t.strip()) >= 3]


class Visit(models.Model):
    """One check-in: reason for visit, vitals, queue ticket and the doctor's notes."""

    WAITING = "waiting"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (WAITING, "Waiting"),
        (IN_CONSULTATION, "In consultation"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="visits")
    reason = models.TextField("Reason for visit")
    # Unguessable token in the ticket QR code: opens the visit for logged-in
    # staff, and the registration form for the patient.
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    queue_date = models.DateField(null=True, blank=True, db_index=True)
    queue_number = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WAITING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    diagnosis = models.TextField(blank=True)
    diagnosis_code = models.CharField("ICD-10 code", max_length=10, blank=True)
    doctor_notes = models.TextField(blank=True)
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    diagnosed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["queue_date", "queue_number"],
                condition=~models.Q(queue_number=""),
                name="unique_queue_number_per_day",
            )
        ]

    def __str__(self):
        return f"{self.queue_number or 'Visit'} · {self.patient.name}"

    @property
    def is_open(self):
        return self.status in (self.WAITING, self.IN_CONSULTATION)


class Measurement(models.Model):
    SOURCE_DEVICE = "device"
    SOURCE_MANUAL = "manual"
    SOURCE_PATIENT = "patient"
    SOURCE_SIMULATED = "simulated"
    SOURCE_CHOICES = [
        (SOURCE_DEVICE, "Medical device"),
        (SOURCE_MANUAL, "Entered by staff"),
        (SOURCE_PATIENT, "Reported by patient"),
        (SOURCE_SIMULATED, "Simulated (testing only)"),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="measurements"
    )
    visit = models.ForeignKey(
        Visit, null=True, blank=True, on_delete=models.SET_NULL, related_name="measurements"
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


class PrescriptionItem(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="prescriptions")
    drug = models.CharField(max_length=120)
    dose = models.CharField(max_length=60, help_text="e.g. 500 mg")
    frequency = models.CharField(max_length=60, help_text="e.g. 3x daily after meals")
    duration = models.CharField(max_length=60, blank=True, help_text="e.g. 5 days")
    instructions = models.CharField(max_length=200, blank=True)
    allergy_override = models.BooleanField(default=False, help_text="Prescribed despite an allergy warning")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.drug} {self.dose}"


class PatientSubmission(models.Model):
    """Registration details a patient sent from their phone, awaiting staff review."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [(PENDING, "Pending review"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="submissions")
    visit = models.ForeignKey(Visit, null=True, on_delete=models.SET_NULL, related_name="+")
    data = models.JSONField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-submitted_at"]


class AuditEvent(models.Model):
    """Who changed which medical or registration data, and when."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=40)
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    visit = models.ForeignKey(Visit, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at}"

    @classmethod
    def record(cls, actor, action, patient=None, visit=None, **detail):
        return cls.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            patient=patient or (visit.patient if visit else None),
            visit=visit,
            detail=detail,
        )


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


class GatewayCommand(models.Model):
    """A device-management action requested from the staff Devices page.

    The BLE gateway picks pending commands up with its heartbeat, runs them on
    the server's Bluetooth adapter and reports the result back.
    """

    SCAN = "scan"
    PAIR = "pair"
    TEST = "test"
    REMOVE = "remove"
    ACTION_CHOICES = [
        (SCAN, "Scan for devices"),
        (PAIR, "Pair device"),
        (TEST, "Test connection"),
        (REMOVE, "Remove device"),
    ]

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
    ]

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} ({self.get_status_display()})"


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
