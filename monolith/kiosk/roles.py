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
ROLE_LABELS = dict(ROLE_CHOICES)


def is_doctor(user):
    """Doctors (members of the Doctor group) record diagnoses and prescriptions."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=DOCTOR_GROUP).exists()
    )


def role_of(user):
    if user.is_superuser:
        return "admin"
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
