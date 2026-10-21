from django.conf import settings

from .models import PatientSubmission
from .roles import is_doctor


def app_settings(request):
    """Values every page needs: the clinic time zone and the user's role badges."""
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated)
    return {
        "app_time_zone": settings.TIME_ZONE,
        "user_is_doctor": signed_in and is_doctor(user),
        "pending_submissions": (
            PatientSubmission.objects.filter(status=PatientSubmission.PENDING).count() if signed_in else 0
        ),
    }
