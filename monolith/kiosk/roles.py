from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group

DOCTOR_GROUP = "Doctor"
NURSE_GROUP = "Nurse"

# Roles staff accounts can have. Each maps to Django's flags and groups:
#   admin      superuser: everything, including staff accounts and settings
#   doctor     Doctor group: records diagnoses and prescriptions
#   nurse      Nurse group + is_staff: also manages devices and merges records
#   frontdesk  no group: registers patients and reviews registrations
ROLE_CHOICES = [
    ("doctor", "Doctor"),
    ("nurse", "Nurse"),
    ("frontdesk", "Front desk"),
    ("admin", "Administrator"),
]
ROLE_LABELS = {**dict(ROLE_CHOICES), "patient": "Patient"}
STAFF_ROLES = {"doctor", "nurse", "frontdesk", "admin"}


# What each role may do. Views enforce these; the navigation only shows what is allowed.
CAPABILITIES = {
    # Any clinic staff member; never patients signed in to their portal.
    "staff_area": STAFF_ROLES,
    "use_kiosk": {"nurse", "frontdesk", "admin"},
    "register_patients": {"nurse", "frontdesk", "admin"},
    "review_registrations": {"nurse", "frontdesk", "admin"},
    "scan_tickets": {"nurse", "frontdesk", "admin"},
    "consultations": {"doctor", "nurse", "admin"},
    "merge_patients": {"nurse", "admin"},
    "cancel_visits": {"doctor", "nurse", "admin"},
    "manage_devices": {"nurse", "admin"},
    "manage_staff": {"admin"},
}


def can(user, capability):
    return bool(user.is_authenticated and user.is_active and role_of(user) in CAPABILITIES[capability])


def patient_of(user):
    """The Patient whose portal account `user` is, or None for staff."""
    try:
        return user.patient_record
    except Exception:  # RelatedObjectDoesNotExist, or an anonymous user
        return None


def is_doctor(user):
    """Doctors (members of the Doctor group) record diagnoses and prescriptions."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=DOCTOR_GROUP).exists()
    )


def role_of(user):
    if user.is_superuser:
        return "admin"
    if patient_of(user) is not None:
        return "patient"
    names = {g.name for g in user.groups.all()}
    if DOCTOR_GROUP in names:
        return "doctor"
    if NURSE_GROUP in names:
        return "nurse"
    return "frontdesk"


def apply_role(user, role):
    """Set the user's flags and groups for `role`. The user must be saved first."""
    user.is_superuser = role == "admin"
    user.is_staff = role in ("admin", "nurse")
    user.save(update_fields=["is_superuser", "is_staff"])
    user.groups.remove(*Group.objects.filter(name__in=[DOCTOR_GROUP, NURSE_GROUP]))
    if role == "doctor":
        user.groups.add(Group.objects.get_or_create(name=DOCTOR_GROUP)[0])
    elif role == "nurse":
        user.groups.add(Group.objects.get_or_create(name=NURSE_GROUP)[0])


class DoctorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_doctor(self.request.user)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class CapabilityRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to the roles that have `capability`."""

    capability = None

    def test_func(self):
        return can(self.request.user, self.capability)


class StaffAreaMixin(CapabilityRequiredMixin):
    """Any clinic staff role; patients signed in to the portal are refused."""

    capability = "staff_area"


class PatientPortalMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only the patient whose portal account is signed in."""

    login_url = "portal-login"

    def test_func(self):
        patient = patient_of(self.request.user)
        return patient is not None and patient.is_active and self.request.user.is_active

    @property
    def patient(self):
        return patient_of(self.request.user)
