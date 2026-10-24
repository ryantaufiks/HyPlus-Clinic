from django.conf import settings

from .models import BookingRequest, PartnerInquiry, PatientSubmission, Review
from .queue import CANCEL_REASONS
from .roles import CAPABILITIES, ROLE_LABELS, can, is_doctor, role_of


# Pages under the grouped menus, to highlight the group that holds the current page.
FRONT_DESK_PAGES = {"home", "qr-scanner", "submissions", "submission-review", "bookings", "reviews"}
SETTINGS_PAGES = {"settings", "devices", "staff-list", "staff-create", "staff-edit", "schedules", "staff-schedule"}


def app_settings(request):
    """Values every page needs: the clinic time zone and the user's role badges."""
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated)
    context = {
        "front_desk_pages": FRONT_DESK_PAGES,
        "settings_pages": SETTINGS_PAGES,
        "app_time_zone": settings.TIME_ZONE,
        "cancel_reasons": CANCEL_REASONS,
        "user_is_doctor": signed_in and is_doctor(user),
        "user_role": ROLE_LABELS[role_of(user)] if signed_in else "",
        "user_can": {name: can(user, name) for name in CAPABILITIES} if signed_in else {},
        "pending_submissions": (
            PatientSubmission.objects.filter(status=PatientSubmission.PENDING).count()
            if signed_in and can(user, "review_registrations")
            else 0
        ),
        "new_bookings": (
            BookingRequest.objects.filter(status=BookingRequest.NEW).count() if signed_in and can(user, "manage_bookings") else 0
        ),
        "pending_reviews": (
            Review.objects.filter(status=Review.PENDING).count() if signed_in and can(user, "moderate_reviews") else 0
        ),
    }
    context["new_inquiries"] = (
        PartnerInquiry.objects.filter(status=PartnerInquiry.NEW).count() if signed_in and can(user, "manage_staff") else 0
    )
    context["front_desk_badge"] = context["pending_submissions"] + context["new_bookings"] + context["pending_reviews"]
    return context
