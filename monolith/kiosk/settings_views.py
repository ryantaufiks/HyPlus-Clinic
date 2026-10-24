"""Settings home: every configuration module as a card, grouped like an ERP app launcher.

Each module names the capability it needs; a user only sees the modules they can open.
Modules that are not built yet are listed under "Coming soon" so the layout already has
room for them.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.views.generic import TemplateView

from .models import KioskDevice, PartnerInquiry, Review, Service, SiteConfiguration
from .roles import can
from .schedule_views import doctors

User = get_user_model()

SUPERUSER = "superuser"  # modules only a superuser may open (Django admin, secrets)


def _allowed(user, need):
    return user.is_superuser if need == SUPERUSER else can(user, need)


def can_open_settings(user):
    return can(user, "manage_devices") or can(user, "manage_staff")


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else plural or word + 's'}"


def _modules():
    """(group, modules). A module's `stat`, `badge` and `warn` are called only if the user can open it.

    `badge` counts items waiting for someone; `warn` means the module still needs setting up.
    """
    return [
        ("People", [
            {"title": "Staff accounts", "icon": "bi-person-badge", "tone": "teal", "need": "manage_staff",
             "url": reverse("kiosk:staff-list"), "text": "Doctors, nurses and front desk: roles, rooms and sign-in.",
             "stat": lambda: _plural(User.objects.filter(is_active=True, patient_record__isnull=True).count(), "active account")},
            {"title": "Doctor schedules", "icon": "bi-calendar-week", "tone": "blue", "need": "staff_area",
             "url": reverse("kiosk:schedules"), "text": "Weekly consulting hours and days off for every doctor.",
             "stat": lambda: _plural(doctors().count(), "doctor")},
        ]),
        ("Clinic & website", [
            {"title": "Services & prices", "icon": "bi-tags", "tone": "amber", "need": "manage_staff",
             "url": reverse("admin:kiosk_service_changelist"), "text": "What patients can book, with prices and photos.",
             "stat": lambda: _plural(Service.objects.filter(is_active=True).count(), "active service")},
            {"title": "Patient reviews", "icon": "bi-star", "tone": "rose", "need": "moderate_reviews",
             "url": reverse("kiosk:reviews"), "text": "Approve reviews before they appear on the website.",
             "badge": lambda: Review.objects.filter(status=Review.PENDING).count(), "badge_label": "to review",
             "stat": lambda: _plural(Review.objects.filter(status=Review.APPROVED).count(), "published review")},
            {"title": "Partner inquiries", "icon": "bi-envelope-paper", "tone": "violet", "need": "manage_staff",
             "url": reverse("admin:kiosk_partnerinquiry_changelist"), "text": "Messages from the platform page's contact form.",
             "badge": lambda: PartnerInquiry.objects.filter(status=PartnerInquiry.NEW).count(), "badge_label": "new",
             "stat": lambda: _plural(PartnerInquiry.objects.count(), "inquiry", "inquiries")},
        ]),
        ("Devices & screens", [
            {"title": "Medical devices", "icon": "bi-bluetooth", "tone": "teal", "need": "manage_devices",
             "url": reverse("kiosk:devices"), "text": "Pair, test and monitor the Bluetooth health-check devices.",
             "stat": lambda: "Bluetooth gateway"},
            {"title": "Kiosk screens", "icon": "bi-display", "tone": "blue", "need": "manage_devices",
             "url": reverse("kiosk:devices") + "#kiosks", "text": "Tablets allowed to check patients in.",
             "stat": lambda: _plural(KioskDevice.objects.filter(is_active=True).count(), "active kiosk"),
             "warn": lambda: not KioskDevice.objects.filter(is_active=True).exists()},
            {"title": "Door access", "icon": "bi-door-open", "tone": "slate", "need": "scan_tickets",
             "url": reverse("kiosk:qr-scanner"), "text": "Scan queue tickets at the consulting-room door.",
             "stat": lambda: "QR ticket scanner"},
            {"title": "Waiting-room TV", "icon": "bi-tv", "tone": "green", "need": "staff_area",
             "url": reverse("kiosk:display"), "text": "Open on the smart TV to call numbers with a chime.",
             "stat": lambda: "Opens in a new tab", "new_tab": True},
        ]),
        ("System", [
            {"title": "AI & system settings", "icon": "bi-stars", "tone": "violet", "need": SUPERUSER,
             "url": reverse("admin:kiosk_siteconfiguration_changelist"), "text": "The OpenAI key for AI summaries, and server secrets.",
             "stat": lambda: "OpenAI key set" if SiteConfiguration.load().openai_api_key_hint else "OpenAI key not set",
             "warn": lambda: not SiteConfiguration.load().openai_api_key_hint},
            {"title": "Audit log", "icon": "bi-journal-check", "tone": "slate", "need": SUPERUSER,
             "url": reverse("admin:kiosk_auditevent_changelist"), "text": "Every change to medical and registration data.",
             "stat": lambda: "Read only"},
            {"title": "Admin panel", "icon": "bi-sliders", "tone": "slate", "need": SUPERUSER,
             "url": reverse("admin:index"), "text": "Every record in the database, for advanced changes.",
             "stat": lambda: "Django admin"},
        ]),
    ]


COMING_SOON = [
    {"title": "Staff attendance", "icon": "bi-fingerprint", "text": "Clock in and out with location or QR check, with monthly reports for payroll."},
    {"title": "Video consultation", "icon": "bi-camera-video", "text": "Private video calls for follow-ups, from the doctor's workspace."},
]


class SettingsHomeView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "kiosk/settings_home.html"

    def test_func(self):
        return can_open_settings(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        groups = []
        for title, modules in _modules():
            visible = []
            for module in modules:
                if not _allowed(user, module["need"]):
                    continue
                visible.append({
                    **module,
                    "stat": module["stat"](),
                    "badge": module["badge"]() if "badge" in module else 0,
                    "warn": module["warn"]() if "warn" in module else False,
                })
            if visible:
                groups.append({"title": title, "modules": visible})
        context["groups"] = groups
        context["coming_soon"] = COMING_SOON
        return context
