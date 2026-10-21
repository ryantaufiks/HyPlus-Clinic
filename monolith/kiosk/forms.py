import datetime as dt
import re

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Patient, PrescriptionItem, Visit
from .roles import ROLE_CHOICES

PROFILE_FIELDS = [
    "name",
    "id_type",
    "id_last4",
    "phone",
    "date_of_birth",
    "height_cm",
    "address",
    "has_drug_allergy",
    "drug_allergies",
    "medical_history",
]

class BootstrapMixin:
    """Bootstrap classes on every widget, and is-invalid on fields with errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        # Validate only when asked, never in __init__: subclasses still adjust
        # choices and querysets after calling super().__init__().
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


ALLERGY_CHOICES = [("", "Select…"), ("no", "No known drug allergy"), ("yes", "Yes, allergic to a drug")]


class PatientProfileForm(BootstrapMixin, forms.ModelForm):
    """Registration details, used by staff and (as PatientSelfForm) by patients."""

    has_drug_allergy = forms.TypedChoiceField(
        label="Drug allergy",
        choices=ALLERGY_CHOICES,
        coerce=lambda v: {"yes": True, "no": False}.get(v),
        empty_value=None,
    )
    weight_kg = forms.FloatField(
        label="Weight (kg)", required=False, min_value=2, max_value=300,
        widget=forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
    )

    class Meta:
        model = Patient
        fields = PROFILE_FIELDS
        labels = {
            "id_type": "ID document",
            "id_last4": "Last 4 characters of ID number",
            "date_of_birth": "Date of birth",
            "medical_history": "Medical history",
            "drug_allergies": "Which drugs?",
        }
        help_texts = {
            "id_last4": "For your privacy only the last 4 characters are stored.",
            "medical_history": "Ongoing conditions, past surgeries, medicines you take regularly.",
            "drug_allergies": "Separate several drugs with commas, e.g. penicillin, ibuprofen.",
        }
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "height_cm": forms.NumberInput(attrs={"step": "0.1", "inputmode": "decimal"}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "drug_allergies": forms.Textarea(attrs={"rows": 2}),
            "medical_history": forms.Textarea(attrs={"rows": 4}),
            "id_last4": forms.TextInput(attrs={"maxlength": 4, "autocomplete": "off", "style": "max-width: 8rem"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.has_drug_allergy is not None:
            self.initial["has_drug_allergy"] = "yes" if self.instance.has_drug_allergy else "no"
        for name in ("id_type", "id_last4", "phone", "date_of_birth"):
            self.fields[name].required = True
        self.fields["id_type"].choices = [("", "Select…")] + Patient.ID_TYPE_CHOICES

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter the full name.")
        return name

    def clean_id_last4(self):
        value = self.cleaned_data["id_last4"].strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{4}", value):
            raise forms.ValidationError("Enter exactly the last 4 letters or digits.")
        return value

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        if not re.fullmatch(r"\+?[0-9][0-9 \-]{6,18}", value):
            raise forms.ValidationError("Enter a valid phone number, e.g. +62 812 3456 7890.")
        return value

    def clean_date_of_birth(self):
        value = self.cleaned_data["date_of_birth"]
        today = timezone.localdate()
        if value and (value > today or value < today - dt.timedelta(days=125 * 365)):
            raise forms.ValidationError("Enter a valid date of birth.")
        return value

    def clean_height_cm(self):
        value = self.cleaned_data["height_cm"]
        if value is not None and not 40 <= value <= 250:
            raise forms.ValidationError("Enter the height in centimetres (40–250).")
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("has_drug_allergy") is True and not cleaned.get("drug_allergies", "").strip():
            self.add_error("drug_allergies", "List the drugs the patient is allergic to.")
        if cleaned.get("has_drug_allergy") is False:
            cleaned["drug_allergies"] = ""
        return cleaned

    def submission_data(self):
        """Cleaned values as JSON for a PatientSubmission."""
        data = {}
        for name in PROFILE_FIELDS + ["weight_kg"]:
            value = self.cleaned_data.get(name)
            data[name] = value.isoformat() if isinstance(value, dt.date) else value
        return data


class PatientSelfForm(PatientProfileForm):
    """The same form, worded for a patient filling it in on their phone."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Full name"
        self.fields["medical_history"].label = "Your medical history"
        self.fields["drug_allergies"].label = "Which drugs are you allergic to?"
        self.fields["has_drug_allergy"].label = "Are you allergic to any medicine?"
        self.fields["has_drug_allergy"].choices = [("", "Select…"), ("no", "No"), ("yes", "Yes")]


class DiagnosisForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Visit
        fields = ["diagnosis", "diagnosis_code", "doctor_notes"]
        labels = {"doctor_notes": "Notes (not printed)"}
        widgets = {
            "diagnosis": forms.Textarea(attrs={"rows": 3}),
            "doctor_notes": forms.Textarea(attrs={"rows": 3}),
            "diagnosis_code": forms.TextInput(attrs={"placeholder": "e.g. I10", "style": "max-width: 10rem"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["diagnosis"].required = True

    def clean_diagnosis_code(self):
        return self.cleaned_data["diagnosis_code"].strip().upper()


class PrescriptionItemForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PrescriptionItem
        fields = ["drug", "dose", "frequency", "duration", "instructions"]
        widgets = {
            "drug": forms.TextInput(attrs={"placeholder": "Drug name"}),
            "dose": forms.TextInput(attrs={"placeholder": "500 mg"}),
            "frequency": forms.TextInput(attrs={"placeholder": "3x daily"}),
            "duration": forms.TextInput(attrs={"placeholder": "5 days"}),
            "instructions": forms.TextInput(attrs={"placeholder": "After meals"}),
        }


PrescriptionFormSet = forms.inlineformset_factory(
    Visit, PrescriptionItem, form=PrescriptionItemForm, extra=1, can_delete=True
)


def allergy_conflicts(patient, drug_names):
    """Drug names that match one of the patient's recorded allergies (case-insensitive)."""
    terms = [t.lower() for t in patient.allergy_terms()]
    conflicts = []
    for drug in drug_names:
        lowered = drug.lower()
        if any(term in lowered or lowered in term for term in terms):
            conflicts.append(drug)
    return conflicts


class StaffAccountForm(BootstrapMixin, forms.ModelForm):
    """Create or edit a staff account. Passwords are set by the staff member via a setup link."""

    role = forms.ChoiceField(choices=ROLE_CHOICES)
    room = forms.CharField(
        label="Consulting room", max_length=40, required=False,
        help_text="For doctors: shown on the waiting-room TV, e.g. Room 1.",
    )

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name", "username", "email"]
        labels = {"email": "Email (optional)"}
        help_texts = {"username": "Used to log in. Letters, digits and . _ - only."}

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        if editing_self:
            # An administrator cannot remove their own administrator role.
            self.fields["role"].disabled = True

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("role") == "doctor" and not cleaned.get("room", "").strip():
            self.add_error("room", "Enter the doctor's consulting room.")
        return cleaned

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if not re.fullmatch(r"[a-z0-9._-]{3,30}", username):
            raise forms.ValidationError("Use 3–30 letters, digits, dots, dashes or underscores.")
        if username.startswith("patient-"):
            raise forms.ValidationError("Usernames starting with “patient-” are reserved for patient accounts.")
        return username
