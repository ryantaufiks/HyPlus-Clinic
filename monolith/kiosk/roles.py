from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

DOCTOR_GROUP = "Doctor"


def is_doctor(user):
    """Doctors (members of the Doctor group) record diagnoses and prescriptions."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=DOCTOR_GROUP).exists()
    )


class DoctorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_doctor(self.request.user)
