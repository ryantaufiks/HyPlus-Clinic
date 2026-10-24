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
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from . import queue, schedule
from .forms import BootstrapMixin
from .kiosk_api import assign_queue_number
from .models import AuditEvent, BookingRequest, PartnerInquiry, Patient, Review, Service, Visit
from .portal_views import whatsapp_number
from .queue_views import _doctor_face, _doctor_name
from .roles import DOCTOR_GROUP, CapabilityRequiredMixin, PatientPortalMixin, can, patient_of

BOOKING_DAYS_AHEAD = 60


def bookable_doctors():
    return (
        get_user_model()
        .objects.filter(is_active=True, groups__name=DOCTOR_GROUP)
        .order_by("first_name", "last_name", "username")
    )


def approved_reviews():
    return Review.objects.filter(status=Review.APPROVED).select_related("patient", "visit__doctor")


# Shown only to signed-in staff, labelled "Preview", while no real review is
# approved: lets the clinic see the section without ever showing invented
# reviews to the public as if patients wrote them.
SAMPLE_REVIEWS = [
    ("Sarah L.", 5, "Took a number from home and only came in when I was nearly up. The doctor already had my readings."),
    ("Budi H.", 5, "Check-in at the kiosk was quick and easy, even for my father. Very well organised clinic."),
    ("Mei Ling T.", 4, "Short wait and a thorough doctor. My prescription was in the portal right after the visit."),
    ("Rizky P.", 5, "Love seeing my queue position on my phone. No more sitting in the waiting room for an hour."),
    ("Ayu S.", 5, "The doctor explained my blood pressure results clearly and the follow-up booking took a minute."),
    ("Daniel W.", 4, "Clean, modern and efficient. Booking on WhatsApp was confirmed the same morning."),
    ("Nur A.", 5, "Friendly staff and no paperwork. Everything from my last visits is in one place."),
    ("Kevin O.", 5, "Fast, professional and on time. Exactly what a clinic visit should feel like."),
]


def _initials(name):
    return "".join(part[0] for part in name.replace(".", "").split()[:2]).upper()


def review_cards(reviews):
    return [
        {
            "name": r.display_name,
            "initials": _initials(r.display_name),
            "rating": r.rating,
            "comment": r.comment,
            "when": r.created_at,
        }
        for r in reviews
    ]


def review_summary(ratings):
    count = len(ratings)
    average = sum(ratings) / count if count else None
    return {
        "count": count,
        "average": average,
        "stars": round(average or 0),
        "bars": [
            {"stars": n, "count": ratings.count(n), "percent": round(100 * ratings.count(n) / count) if count else 0}
            for n in range(5, 0, -1)
        ],
    }


# --- Platform page (/): Hy+ Clinic for clinics, brands and partners ---------------------------

# Connected health-check devices: "live" ones show as Integrated, the rest as Coming soon.
DEVICES = [
    {"name": "Blood pressure monitor", "icon": "bi-heart-pulse", "detail": "Blood pressure and pulse", "live": True},
    {"name": "Body weight scale", "icon": "bi-speedometer2", "detail": "Weight, with BMI from height", "live": True},
    {"name": "Pulse oximeter", "icon": "bi-activity", "detail": "Oxygen saturation (SpO₂) and pulse", "live": True},
    {"name": "Body thermometer", "icon": "bi-thermometer-half", "detail": "Body temperature", "live": True},
    {"name": "Blood glucose meter", "icon": "bi-droplet-half", "detail": "Blood sugar", "live": True},
    {"name": "Cholesterol meter", "icon": "bi-droplet", "detail": "Total cholesterol", "live": True},
    {"name": "Uric acid meter", "icon": "bi-eyedropper", "detail": "Uric acid", "live": True},
]

# What a clinic gets, shown in the hero card.
PLATFORM_MODULES = [
    {"name": "Health-check devices", "icon": "bi-heart-pulse"},
    {"name": "Digital medical records", "icon": "bi-journal-medical"},
    {"name": "Secure video consultation", "icon": "bi-camera-video"},
    {"name": "Queue display on smart TV", "icon": "bi-tv"},
    {"name": "Room access control", "icon": "bi-door-open"},
    {"name": "Staff attendance", "icon": "bi-fingerprint"},
    {"name": "AI assistant for doctors", "icon": "bi-stars"},
]

# "From manual to digital": what each step looked like before, and with Hy+ Clinic.
SHIFTS = [
    ("Vitals measured, written down, then typed again", "Readings go from the device straight into the record", "bi-heart-pulse"),
    ("Paper files and notes scattered across desks", "One digital medical record: history, ICD-10 diagnoses, prescriptions", "bi-journal-medical"),
    ("Doctors read through notes before each patient", "An AI summary is ready before the patient walks in", "bi-stars"),
    ("A trip to the clinic for every follow-up", "Secure video consultations from home", "bi-camera-video"),
    ("Bookings by phone, confirmed by hand", "Online booking and queue numbers, confirmed on WhatsApp", "bi-calendar2-check"),
    ("Names called out across a crowded room", "Numbers on the patient's phone and the smart TV, with a chime", "bi-tv"),
    ("Keys, and staff walking patients to rooms", "QR tickets and staff accounts open the right doors", "bi-door-open"),
    ("Paper sign-in sheets for attendance", "Digital clock-in, matched with each schedule", "bi-fingerprint"),
]

# "Built for the people who deliver care": what each role gains.
ROLES = [
    {"name": "Doctors", "icon": "bi-clipboard2-pulse", "gain": "Fully prepared for every patient.",
     "items": ["Vitals, history and allergies on one screen", "AI pre-consultation summary", "Video consultations from the same workspace", "Prescriptions checked against allergies"]},
    {"name": "Nurses", "icon": "bi-heart-pulse", "gain": "Less recording, more caring.",
     "items": ["Patients measure themselves at the kiosk", "Abnormal readings flagged automatically", "Urgent patients moved to the front", "No transcription mistakes"]},
    {"name": "Front desk", "icon": "bi-person-badge", "gain": "A calmer counter.",
     "items": ["Self check-in and online queue numbers", "Bookings confirmed on WhatsApp", "Queue on the smart TV, not shouted", "Registrations approved in one click"]},
    {"name": "Clinic owners", "icon": "bi-graph-up-arrow", "gain": "The whole clinic at a glance.",
     "items": ["Live dashboard of visits and devices", "Staff attendance and doctor schedules", "Room access managed in one place", "Your brand on every screen"]},
]

# Brands shown in "Works with the brands you already use". The logos in static/img/brands/ are
# single-colour masks (transparent PNG, 112 px high) so the page can tint them with CSS.
BRAND_GROUPS = [
    {"title": "Health-check devices", "icon": "bi-heart-pulse", "brands": [
        ("OMRON", "omron", 470, 95), ("Beurer", "beurer", 423, 112), ("Yuwell", "yuwell", 311, 112),
        ("FORA", "fora", 283, 112), ("ABN", "abn", 470, 87), ("Stemoscope", "stemoscope", 443, 112),
    ]},
    {"title": "Door access, CCTV and smart relays", "icon": "bi-door-open", "brands": [
        ("Hikvision", "hikvision", 470, 61), ("Dahua", "dahua", 371, 112), ("Axis", "axis", 311, 112),
        ("Shelly", "shelly", 405, 112), ("Sonoff", "sonoff", 372, 112),
    ]},
]
# Optical sizing: a wide, thin wordmark gets a shorter box than a compact one, so every logo
# carries about the same visual weight (height scales with 1/sqrt(aspect ratio)).
for _group in BRAND_GROUPS:
    _group["brands"] = [
        {"name": name, "file": f"img/brands/{slug}.png", "height": round(min(46, max(24, 34 * (3 / (w / h)) ** 0.5)))}
        for name, slug, w, h in _group["brands"]
    ]


class PartnerInquiryForm(BootstrapMixin, forms.ModelForm):
    consent = forms.BooleanField(label="I agree that Hy+ Clinic stores these details to reply to me.")
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = PartnerInquiry
        fields = ["name", "email", "phone", "organisation", "interest", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "Optional"}),
            "organisation": forms.TextInput(attrs={"autocomplete": "organization", "placeholder": "Optional"}),
            "message": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us about your clinic or project"}),
        }
        labels = {"name": "Your name", "interest": "I'm interested in"}

    def clean_message(self):
        value = self.cleaned_data["message"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Please tell us a little more.")
        return value


@method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True), name="post")
class PlatformView(View):
    template_name = "kiosk/platform.html"

    def _render(self, request, form, sent=False):
        return render(request, self.template_name, {"form": form, "sent": sent, "devices": DEVICES, "modules": PLATFORM_MODULES, "shifts": SHIFTS, "roles": ROLES, "brand_groups": BRAND_GROUPS})

    def get(self, request):
        interest = request.GET.get("interest")
        initial = {"interest": interest} if interest in dict(PartnerInquiry.INTEREST_CHOICES) else {}
        return self._render(request, PartnerInquiryForm(initial=initial))

    def post(self, request):
        form = PartnerInquiryForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)
        if not form.cleaned_data.get("website"):  # bots fill in the hidden field
            inquiry = form.save(commit=False)
            inquiry.consent_at = timezone.now()
            inquiry.save()
        return self._render(request, PartnerInquiryForm(), sent=True)


# --- Demo clinic (/demo/) ---------------------------------------------------------------------


def service_image(request, pk):
    """The picture of an active service (public: it is shown on the home page)."""
    service = get_object_or_404(Service, pk=pk, is_active=True)
    if not service.image:
        raise Http404
    response = FileResponse(service.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "public, max-age=604800"  # the URL changes with every new upload
    return response


class LandingView(TemplateView):
    template_name = "kiosk/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = list(Service.objects.filter(is_active=True, is_featured=True))
        on_duty = queue.doctors_on_duty()
        hours = schedule.hours_for([d for d, _ in on_duty], timezone.localdate())
        reviews = list(approved_reviews()[:16])
        ratings = list(approved_reviews().values_list("rating", flat=True))
        preview = not reviews and can(self.request.user, "staff_area")
        if preview:
            cards = [
                {"name": n, "initials": _initials(n), "rating": r, "comment": c, "when": None}
                for n, r, c in SAMPLE_REVIEWS
            ]
            ratings = [r for _, r, _ in SAMPLE_REVIEWS]
        else:
            cards = review_cards(reviews)
        context.update(
            {
                "services": services,
                "from_price": min((s.price_sgd for s in services), default=None),
                "doctors_today": [
                    {"name": _doctor_name(d), "room": room, "face": _doctor_face(d), "hours": schedule.format_blocks(hours[d.pk])}
                    for d, room in on_duty
                ],
                "reviews": cards,
                # Two rows that scroll in opposite directions.
                "review_rows": [cards[0::2], cards[1::2]] if len(cards) >= 6 else [cards],
                "reviews_preview": preview,
                "review_summary": review_summary(ratings),
            }
        )
        return context


# --- Booking (public) --------------------------------------------------------------------------


QUEUE_SERVICE_SLUG = "clinic-consultation"


class BookingForm(BootstrapMixin, forms.ModelForm):
    """One form for every service.

    A clinic consultation for today gives a queue number straight away (an
    online ticket, called once the patient checks in); everything else is a
    booking request that staff confirm on WhatsApp.
    """

    patient_id = forms.CharField(
        label="Patient ID (if you have one)", max_length=6, required=False,
        widget=forms.TextInput(attrs={"autocapitalize": "characters", "autocomplete": "off", "placeholder": "e.g. 58MPQ"}),
        help_text="Links the visit to your records. It must match the WhatsApp number we have for you.",
    )
    consent = forms.BooleanField(label="I agree that the clinic stores these details for my visit or booking.")
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
        labels = {"preferred_doctor": "Doctor", "preferred_date": "Date", "preferred_time": "Preferred time", "name": "Full name"}

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
        self.fields["preferred_time"].required = False  # not needed for a queue number today
        self.is_queue_ticket = False

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

    def clean(self):
        data = super().clean()
        service, date = data.get("service"), data.get("preferred_date")
        self.is_queue_ticket = bool(service and service.slug == QUEUE_SERVICE_SLUG and date == timezone.localdate())
        data["patient"] = None
        if self.is_queue_ticket:
            self._clean_queue_ticket(data)
        elif date and not data.get("preferred_time"):
            self.add_error("preferred_time", "Choose a time of day.")
        elif date:
            problem = schedule.availability_error(data.get("preferred_doctor"), date, data.get("preferred_time"))
            if problem:
                self.add_error("preferred_doctor", problem)
        return data

    def _clean_queue_ticket(self, data):
        on_duty = {d.pk for d, _ in queue.doctors_on_duty()}
        if not on_duty:
            raise forms.ValidationError("No doctors are on duty right now, so we cannot give a queue number for today. Please choose another day.")
        doctor = data.get("preferred_doctor")
        if doctor and doctor.pk not in on_duty:
            self.add_error("preferred_doctor", "This doctor is not on duty today. Choose another doctor or the first available.")
        if len(" ".join((data.get("notes") or "").split())) < 3:
            self.add_error("notes", "Tell us briefly why you are coming.")
        phone = data.get("phone")
        if not phone:
            return
        digits = whatsapp_number(phone)
        open_today = Visit.objects.filter(
            queue_date=timezone.localdate(), source=Visit.SOURCE_ONLINE,
            status__in=[Visit.WAITING, Visit.CALLED, Visit.IN_CONSULTATION],
        ).exclude(contact_phone="")
        if any(whatsapp_number(v.contact_phone) == digits for v in open_today.only("contact_phone")):
            raise forms.ValidationError(
                "This WhatsApp number already has a queue number for today. Open the ticket link you received, or ask the front desk."
            )
        patient_id = "".join((data.get("patient_id") or "").split()).upper()
        if patient_id:
            patient = Patient.objects.filter(patient_id=patient_id, is_active=True).first()
            # The phone must match too, so nobody can add visits to someone else's record.
            if patient is None or not patient.phone or whatsapp_number(patient.phone)[-4:] != digits[-4:]:
                self.add_error("patient_id", "That Patient ID does not match this WhatsApp number. Leave it empty to continue as a new patient.")
            else:
                data["patient"] = patient


def create_queue_ticket(data):
    """An online ticket for today: numbered now, called once the patient checks in."""
    with transaction.atomic():
        patient = data["patient"] or Patient.objects.create(name=data["name"], phone=data["phone"])
        visit = Visit.objects.create(
            patient=patient,
            reason=" ".join(data["notes"].split())[:2000],
            requested_doctor=data.get("preferred_doctor"),
            source=Visit.SOURCE_ONLINE,
            checked_in_at=None,
            contact_phone=data["phone"],
        )
    assign_queue_number(visit)
    AuditEvent.record(None, "queue.online_ticket", visit=visit)
    return visit


@method_decorator(ratelimit(key="ip", rate="5/h", method="POST", block=True), name="post")
class BookingView(View):
    template_name = "kiosk/booking.html"

    def _initial(self, request):
        initial = {}
        service = Service.objects.filter(slug=request.GET.get("service"), is_active=True).first()
        if service:
            initial["service"] = service
            if service.slug == QUEUE_SERVICE_SLUG:
                initial["preferred_date"] = timezone.localdate()
        patient = patient_of(request.user) if request.user.is_authenticated else None
        if patient:
            initial.update({"name": patient.name, "phone": patient.phone, "patient_id": patient.patient_id})
        return initial

    def _render(self, request, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "queue_service": Service.objects.filter(slug=QUEUE_SERVICE_SLUG, is_active=True).values_list("pk", flat=True).first(),
                "today": timezone.localdate().isoformat(),
                "queue_open": bool(queue.doctors_on_duty()),
                "doctor_hours": {str(d.pk): schedule.summary(d) for d in bookable_doctors()},
            },
        )

    def get(self, request):
        return self._render(request, BookingForm(initial=self._initial(request)))

    def post(self, request):
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)
        if form.cleaned_data.get("website"):
            return render(request, "kiosk/booking_done.html", {})  # quietly drop bots
        if form.is_queue_ticket:
            visit = create_queue_ticket(form.cleaned_data)
            return redirect(reverse("kiosk:visit-token", args=[visit.token]) + "?new=1")
        booking = form.save(commit=False)
        booking.consent_at = timezone.now()
        if request.user.is_authenticated:
            booking.patient = patient_of(request.user)
        booking.save()
        return render(request, "kiosk/booking_done.html", {"booking": booking, "first_name": booking.name.split()[0]})


def queue_ticket_redirect(request):
    """Old link to the separate queue page: the clinic consultation in the booking form."""
    return redirect(reverse("kiosk:book") + f"?service={QUEUE_SERVICE_SLUG}")


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
