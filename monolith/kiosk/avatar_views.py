"""Uploading and serving profile photos. Photos are never public."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from .avatars import remove_photo, replace_photo
from .models import AuditEvent, Patient, StaffProfile
from .roles import ROLE_LABELS, PatientPortalMixin, StaffAreaMixin, can, patient_of, role_of


def _photo_response(field):
    if not field:
        raise Http404
    response = FileResponse(field.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response


@require_GET
@login_required
def staff_photo(request, user_id):
    """A staff member's photo: visible to anyone signed in (staff and patients)."""
    profile = get_object_or_404(StaffProfile, user_id=user_id)
    return _photo_response(profile.photo)


@require_GET
@login_required
def patient_photo(request, pk):
    """A patient's photo: visible to clinic staff and to the patient themself."""
    patient = get_object_or_404(Patient, pk=pk)
    own = patient_of(request.user)
    if not (can(request.user, "staff_area") or (own is not None and own.pk == patient.pk)):
        raise Http404
    return _photo_response(patient.photo)


def _apply(request, obj, actor_patient=None):
    if request.POST.get("action") == "remove":
        remove_photo(obj)
        messages.info(request, "Photo removed.")
        return
    upload = request.FILES.get("photo")
    if not upload:
        messages.error(request, "Choose a photo to upload.")
        return
    try:
        replace_photo(obj, upload)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return
    AuditEvent.record(request.user, "photo.updated", patient=actor_patient)
    messages.success(request, "Photo updated.")


class MyProfileView(StaffAreaMixin, TemplateView):
    """Staff: own profile photo (doctors, nurses, front desk, administrators)."""

    template_name = "kiosk/my_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"], _ = StaffProfile.objects.get_or_create(user=self.request.user)
        context["role"] = ROLE_LABELS[role_of(self.request.user)]
        return context

    def post(self, request):
        profile, _ = StaffProfile.objects.get_or_create(user=request.user)
        _apply(request, profile)
        return redirect("kiosk:my-profile")


class PortalPhotoView(PatientPortalMixin, View):
    def post(self, request):
        _apply(request, self.patient, actor_patient=self.patient)
        return redirect("portal-home")
