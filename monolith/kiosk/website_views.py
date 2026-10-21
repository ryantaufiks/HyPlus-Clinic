"""Public website: home page, booking requests, and patient reviews.

Booking requests are not appointments: front-desk staff confirm each one with
the patient by WhatsApp. Reviews come only from patients with a completed
visit and are shown on the website after staff approve them.
"""

import datetime as dt
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from . import queue
from .forms import BootstrapMixin
from .models import AuditEvent, BookingRequest, Review, Service, Visit
from .portal_views import whatsapp_number
from .queue_views import _doctor_face, _doctor_name
from .roles import DOCTOR_GROUP, CapabilityRequiredMixin, PatientPortalMixin, patient_of

BOOKING_DAYS_AHEAD = 60


def bookable_doctors():
    return (
        get_user_model()
        .objects.filter(is_active=True, groups__name=DOCTOR_GROUP)
        .order_by("first_name", "last_name", "username")
    )


def approved_reviews():
    return Review.objects.filter(status=Review.APPROVED).select_related("patient", "visit__doctor")


# --- Home page --------------------------------------------------------------------------------


class LandingView(TemplateView):
    template_name = "kiosk/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = list(Service.objects.filter(is_active=True, is_featured=True))
        reviews = approved_reviews()
        summary = reviews.aggregate(average=Avg("rating"), count=Count("id"))
        context.update(
            {
                "services": services,
                "from_price": min((s.price_sgd for s in services), default=None),
                "doctors_today": [
                    {"name": _doctor_name(d), "room": room, "face": _doctor_face(d)} for d, room in queue.doctors_on_duty()
                ],
                "reviews": reviews[:6],
                "review_count": summary["count"],
                "review_average": summary["average"],
                "review_stars": round(summary["average"] or 0),
            }
        )
        return context


# --- Booking (public) --------------------------------------------------------------------------


class BookingForm(BootstrapMixin, forms.ModelForm):
    consent = forms.BooleanField(
        label="I agree that the clinic stores these details to contact me about my booking.",
    )
    # Bots fill in every field; people never see this one.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = BookingRequest
        fields = ["service", "preferred_doctor", "preferred_date", "preferred_time", "name", "phone", "email", "notes"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "preferred_time": forms.RadioSelect,
            "notes": forms.Textarea(attrs={"rows": 3}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "+65 8123 4567"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        labels = {"preferred_doctor": "Doctor", "preferred_date": "Preferred date", "preferred_time": "Preferred time", "name": "Full name"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(is_active=True, is_bookable=True)
        self.fields["service"].required = True
        self.fields["service"].empty_label = "Choose a service…"
        self.fields["preferred_doctor"].queryset = bookable_doctors()
        self.fields["preferred_doctor"].label_from_instance = _doctor_name
        self.fields["preferred_doctor"].empty_label = "First available doctor"
        today = timezone.localdate()
        self.fields["preferred_date"].widget.attrs.update(
            {"min": today.isoformat(), "max": (today + dt.timedelta(days=BOOKING_DAYS_AHEAD)).isoformat()}
        )
        self.fields["preferred_time"].widget.attrs["class"] = "btn-check"
        self.fields["preferred_time"].choices = BookingRequest.TIME_CHOICES  # no empty choice

    def clean_preferred_date(self):
        value = self.cleaned_data["preferred_date"]
        today = timezone.localdate()
        if value < today:
            raise forms.ValidationError("Choose today or a later date.")
        if value > today + dt.timedelta(days=BOOKING_DAYS_AHEAD):
            raise forms.ValidationError(f"Bookings open up to {BOOKING_DAYS_AHEAD} days ahead.")
        return value

    def clean_phone(self):
        value = " ".join(self.cleaned_data["phone"].split())
        if len(whatsapp_number(value)) < 8:
            raise forms.ValidationError("Enter a phone number we can reach on WhatsApp.")
        return value

    def clean_name(self):
        value = " ".join(self.cleaned_data["name"].split())
        if len(value) < 2:
            raise forms.ValidationError("Enter your full name.")
        return value


@method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True), name="post")
class BookingView(View):
    template_name = "kiosk/booking.html"

    def _initial(self, request):
        initial = {}
        service = Service.objects.filter(slug=request.GET.get("service"), is_active=True).first()
        if service:
            initial["service"] = service
        patient = patient_of(request.user) if request.user.is_authenticated else None
        if patient:
            initial.update({"name": patient.name, "phone": patient.phone})
        return initial

    def get(self, request):
        return render(request, self.template_name, {"form": BookingForm(initial=self._initial(request))})

    def post(self, request):
        form = BookingForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        if form.cleaned_data.get("website"):
            return render(request, "kiosk/booking_done.html", {})  # quietly drop bots
        booking = form.save(commit=False)
        booking.consent_at = timezone.now()
        if request.user.is_authenticated:
            booking.patient = patient_of(request.user)
        booking.save()
        return render(request, "kiosk/booking_done.html", {"booking": booking, "first_name": booking.name.split()[0]})


# --- Booking requests (staff) ---------------------------------------------------------------------


def booking_whatsapp_url(booking):
    doctor = _doctor_name(booking.preferred_doctor) if booking.preferred_doctor else "the first available doctor"
    text = (
        f"Hello {booking.name.split()[0]}, this is the clinic about your booking request for "
        f"{booking.service.name if booking.service else 'a consultation'} with {doctor} on "
        f"{booking.preferred_date:%A %d %B} ({booking.get_preferred_time_display()}). "
    )
    return f"https://wa.me/{whatsapp_number(booking.phone)}?text={quote(text)}"


class BookingListView(CapabilityRequiredMixin, TemplateView):
    capability = "manage_bookings"
    template_name = "kiosk/bookings.html"
    TABS = [("open", "To handle"), ("confirmed", "Confirmed"), ("closed", "Closed")]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "open")
        bookings = BookingRequest.objects.select_related("service", "preferred_doctor", "patient", "handled_by")
        if tab == "confirmed":
            bookings = bookings.filter(status=BookingRequest.CONFIRMED).order_by("preferred_date", "preferred_time")
        elif tab == "closed":
            bookings = bookings.filter(status__in=[BookingRequest.DECLINED, BookingRequest.DONE])[:100]
        else:
            tab = "open"
            bookings = bookings.filter(status=BookingRequest.NEW).order_by("preferred_date", "created_at")
        context.update(
            {
                "tab": tab,
                "tabs": self.TABS,
                "rows": [{"booking": b, "whatsapp": booking_whatsapp_url(b)} for b in bookings],
            }
        )
        return context


class BookingUpdateView(CapabilityRequiredMixin, View):
    capability = "manage_bookings"

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, pk=pk)
        status = request.POST.get("status")
        if status not in dict(BookingRequest.STATUS_CHOICES):
            messages.error(request, "Unknown status.")
            return redirect("kiosk:bookings")
        booking.status = status
        booking.staff_note = " ".join(request.POST.get("staff_note", "").split())[:200]
        booking.handled_by = request.user
        booking.handled_at = timezone.now()
        booking.save(update_fields=["status", "staff_note", "handled_by", "handled_at"])
        AuditEvent.record(request.user, f"booking.{status}", patient=booking.patient, booking=booking.pk)
        messages.success(request, f"Booking from {booking.name} marked {booking.get_status_display().lower()}.")
        tab = request.POST.get("tab") if request.POST.get("tab") in dict(BookingListView.TABS) else "open"
        return redirect(reverse("kiosk:bookings") + f"?tab={tab}")


# --- Reviews ---------------------------------------------------------------------------------------


class ReviewForm(BootstrapMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(5, 0, -1)], coerce=int, widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3, "maxlength": 600, "placeholder": "How was your visit?"})}
        labels = {"comment": "Your review"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rating"].widget.attrs["class"] = "btn-check"

    def clean_comment(self):
        value = self.cleaned_data["comment"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Please write at least a short sentence.")
        return value


class PortalReviewView(PatientPortalMixin, View):
    """A patient reviews one of their completed visits (once)."""

    def post(self, request, pk):
        visit = get_object_or_404(Visit, pk=pk, patient=self.patient, status=Visit.COMPLETED)
        if Review.objects.filter(visit=visit).exists():
            messages.info(request, "You have already reviewed this visit.")
            return redirect("portal-home")
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.visit = visit
            review.patient = self.patient
            review.save()
            messages.success(request, "Thank you for your review. It will appear on our website after a quick check.")
        else:
            messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
        return redirect("portal-home")


class ReviewModerationView(CapabilityRequiredMixin, TemplateView):
    capability = "moderate_reviews"
    template_name = "kiosk/reviews.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reviews = Review.objects.select_related("patient", "visit__doctor", "moderated_by")
        context["pending"] = reviews.filter(status=Review.PENDING)
        context["recent"] = reviews.exclude(status=Review.PENDING)[:30]
        return context

    def post(self, request):
        review = get_object_or_404(Review, pk=request.POST.get("review"))
        decision = request.POST.get("decision")
        if decision in (Review.APPROVED, Review.REJECTED, Review.PENDING):
            review.status = decision
            review.moderated_by = request.user
            review.moderated_at = timezone.now()
            review.save(update_fields=["status", "moderated_by", "moderated_at"])
            AuditEvent.record(request.user, f"review.{decision}", patient=review.patient, visit=review.visit)
            messages.success(request, f"Review by {review.display_name} {review.get_status_display().lower()}.")
        return redirect("kiosk:reviews")
