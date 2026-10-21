"""Patient portal: patients see their own visits, vitals, diagnoses and prescriptions.

Staff invite a patient (automatically after approving their registration) by
sending a one-time setup link, exactly like staff accounts. To activate, the
patient confirms their date of birth, agrees to the privacy notice and
chooses a password. They then sign in with their Patient ID.
"""

import re
from urllib.parse import quote

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from .models import AuditEvent, Patient, Visit
from .roles import CapabilityRequiredMixin, PatientPortalMixin, patient_of
from .views import latest_vitals

User = get_user_model()


def portal_username(patient):
    return f"patient-{patient.patient_id.lower()}"


def ensure_portal_user(patient):
    """The patient's portal login, created (without a usable password) if missing."""
    if patient.user_id:
        return patient.user
    user = User(username=portal_username(patient), first_name=patient.name[:150])
    user.set_unusable_password()
    user.save()
    patient.user = user
    patient.save(update_fields=["user"])
    return user


def portal_setup_link(request, user):
    path = reverse(
        "portal-setup",
        kwargs={"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user)},
    )
    return settings.PUBLIC_BASE_URL + path if settings.PUBLIC_BASE_URL else request.build_absolute_uri(path)


def whatsapp_number(phone):
    """Digits for wa.me; a leading 0 is taken as an Indonesian number."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


def render_invite(request, patient, *, approved=False):
    user = ensure_portal_user(patient)
    link = portal_setup_link(request, user)
    days = settings.PASSWORD_RESET_TIMEOUT // 86400
    text = (
        f"Hello {patient.name.split()[0]}, your AIVIN patient account is ready. "
        f"Open this link within {days} days to set your password and see your health records: {link}"
    )
    number = whatsapp_number(patient.phone)
    AuditEvent.record(request.user, "portal.invited", patient=patient)
    return render(
        request,
        "kiosk/portal_invite.html",
        {
            "patient": patient,
            "link": link,
            "valid_days": days,
            "approved": approved,
            "whatsapp_url": f"https://wa.me/{number}?text={quote(text)}" if number else f"https://wa.me/?text={quote(text)}",
            "has_number": bool(number),
        },
    )


# --- Staff -----------------------------------------------------------------------------------


class PortalInviteView(CapabilityRequiredMixin, View):
    """Create a new setup link for a patient (also used to reset their password)."""

    capability = "register_patients"

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        if not patient.date_of_birth:
            messages.error(request, "Add the patient's date of birth first: it is used to verify them when they activate.")
            return redirect("kiosk:patient-detail", patient.pk)
        if patient.user_id and not patient.user.is_active:
            patient.user.is_active = True
            patient.user.save(update_fields=["is_active"])
        return render_invite(request, patient)


class PortalDisableView(CapabilityRequiredMixin, View):
    capability = "register_patients"

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        if patient.user_id:
            patient.user.is_active = False
            patient.user.save(update_fields=["is_active"])
            AuditEvent.record(request.user, "portal.disabled", patient=patient)
            messages.info(request, "Portal access disabled.")
        return redirect("kiosk:patient-detail", patient.pk)


# --- Activation (public, by link) -------------------------------------------------------------


class PortalSetupForm(SetPasswordForm):
    date_of_birth = forms.DateField(label="Your date of birth", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    consent = forms.BooleanField(
        label="I agree that the clinic stores my health data and shows it to me in this portal, as described in the privacy notice.",
    )
    field_order = ["date_of_birth", "new_password1", "new_password2", "consent"]

    def __init__(self, user, patient, *args, **kwargs):
        self.patient = patient
        super().__init__(user, *args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs["class"] = "form-control"

    def clean_date_of_birth(self):
        if self.cleaned_data["date_of_birth"] != self.patient.date_of_birth:
            raise forms.ValidationError("That date of birth does not match our records.")
        return self.cleaned_data["date_of_birth"]


@method_decorator(ratelimit(key="ip", rate="10/h", method="POST", block=True), name="post")
class PortalSetupView(View):
    template_name = "kiosk/portal_setup.html"

    def _user(self, uidb64, token):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return None, None
        patient = patient_of(user)
        if patient is None or not user.is_active or not default_token_generator.check_token(user, token):
            return None, None
        return user, patient

    def get(self, request, uidb64, token):
        user, patient = self._user(uidb64, token)
        if user is None:
            return render(request, self.template_name, {"invalid": True})
        return render(request, self.template_name, {"form": PortalSetupForm(user, patient), "patient": patient})

    def post(self, request, uidb64, token):
        user, patient = self._user(uidb64, token)
        if user is None:
            return render(request, self.template_name, {"invalid": True})
        form = PortalSetupForm(user, patient, request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "patient": patient})
        with transaction.atomic():
            form.save()  # sets the password, which also invalidates the link
            patient.portal_consent_at = timezone.now()
            patient.save(update_fields=["portal_consent_at"])
            AuditEvent.record(user, "portal.activated", patient=patient)
        return redirect(reverse("portal-login") + "?setup=done")


# --- Sign-in ------------------------------------------------------------------------------------


class PortalLoginForm(AuthenticationForm):
    username = forms.CharField(label="Patient ID", max_length=10, widget=forms.TextInput(attrs={"autocapitalize": "characters", "autocomplete": "username"}))

    def clean_username(self):
        patient_id = "".join(self.cleaned_data["username"].split()).upper()
        return f"patient-{patient_id.lower()}"

    def get_invalid_login_error(self):
        return forms.ValidationError("Incorrect Patient ID or password.", code="invalid_login")


class RoleAwareLoginView(LoginView):
    """Staff login; a patient who signs in here is taken to their portal."""

    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        if patient_of(self.request.user) is not None:
            return reverse("portal-home")
        return super().get_default_redirect_url()

    def get_redirect_url(self):
        # Never send a patient on to a staff page from ?next=.
        if patient_of(self.request.user) is not None:
            return ""
        return super().get_redirect_url()


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class PortalLoginView(LoginView):
    template_name = "kiosk/portal_login.html"
    authentication_form = PortalLoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("portal-home")


# --- Portal pages ---------------------------------------------------------------------------------


class PortalHomeView(PatientPortalMixin, TemplateView):
    template_name = "kiosk/portal_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.patient
        visits = list(
            patient.visits.exclude(status=Visit.CANCELLED).prefetch_related("prescriptions", "measurements").select_related("doctor")
        )
        measurements = list(patient.measurements.order_by("-measured_at"))
        oldest_first = list(reversed(measurements))
        reviews = {r.visit_id: r for r in patient.reviews.all()}
        context.update(
            {
                "patient": patient,
                "vitals": latest_vitals(measurements),
                "visits": [
                    {"visit": v, "vitals": latest_vitals(v.measurements.all()), "review": reviews.get(v.pk)} for v in visits
                ],
                "open_visit": next((v for v in visits if v.is_open and v.queue_date == timezone.localdate()), None),
                "chart_data": {
                    "bp": [
                        {"t": m.measured_at.isoformat(), "systolic": m.systolic_bp, "diastolic": m.diastolic_bp, "pulse": m.heart_rate_bpm}
                        for m in oldest_first if m.systolic_bp is not None and m.diastolic_bp is not None
                    ],
                    "weight": [{"t": m.measured_at.isoformat(), "weight": m.weight_kg} for m in oldest_first if m.weight_kg is not None],
                },
            }
        )
        return context


class PortalPrescriptionView(PatientPortalMixin, TemplateView):
    """The patient's own printable prescription (no doctor's notes)."""

    template_name = "kiosk/prescription_print.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit = get_object_or_404(Visit.objects.select_related("doctor"), pk=self.kwargs["pk"], patient=self.patient)
        context.update({"visit": visit, "patient": self.patient, "items": visit.prescriptions.all(), "portal": True})
        return context
