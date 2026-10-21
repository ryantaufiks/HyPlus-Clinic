from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from kiosk.models import Patient, Visit
from kiosk.roles import apply_role

# Pages and who may open them (200) versus who is refused (403).
ACCESS = {
    "kiosk:patient-register": {"nurse", "frontdesk", "admin"},
    "kiosk:submissions": {"nurse", "frontdesk", "admin"},
    "kiosk:qr-scanner": {"nurse", "frontdesk", "admin"},
    "kiosk:doctor-queue": {"doctor", "nurse", "admin"},
    "kiosk:devices": {"nurse", "admin"},
    "kiosk:staff-list": {"admin"},
    "kiosk:dashboard": {"doctor", "nurse", "frontdesk", "admin"},
    "kiosk:patient-list": {"doctor", "nurse", "frontdesk", "admin"},
}
NAV = {"Kiosk": {"nurse", "frontdesk", "admin"}, "Registrations": {"nurse", "frontdesk", "admin"}, "Consultations": {"doctor", "nurse", "admin"}, "Scan ticket": {"nurse", "frontdesk", "admin"}}


class RoleAccessTest(TestCase):
    def login_as(self, role):
        user = get_user_model().objects.create_user(f"user-{role}", password="a-long-password-123")
        apply_role(user, role)
        self.client.force_login(user)
        return user

    def test_page_access_by_role(self):
        for role in ("doctor", "nurse", "frontdesk", "admin"):
            with self.subTest(role=role):
                self.login_as(role)
                for name, allowed in ACCESS.items():
                    status = self.client.get(reverse(name)).status_code
                    self.assertEqual(status, 200 if role in allowed else 403, f"{role} {name}")
                self.client.logout()

    def test_merge_is_nurse_or_admin(self):
        patient = Patient.objects.create(name="X")
        url = reverse("kiosk:patient-merge", args=[patient.pk])
        for role, expected in (("doctor", 403), ("frontdesk", 403), ("nurse", 200)):
            self.login_as(role)
            self.assertEqual(self.client.get(url).status_code, expected, role)
            self.client.logout()

    def test_navigation_matches_role(self):
        for role in ("doctor", "nurse", "frontdesk", "admin"):
            with self.subTest(role=role):
                self.login_as(role)
                page = self.client.get(reverse("kiosk:dashboard")).content.decode()
                for label, allowed in NAV.items():
                    if role in allowed:
                        self.assertIn(label, page, f"{role} should see {label}")
                    else:
                        self.assertNotIn(f"> {label}", page.replace("</i> ", "> ").replace('<span class="d-lg-none">', ""), f"{role} should not see {label}")
                self.client.logout()

    def test_doctor_can_still_open_visit_from_qr_link(self):
        visit = Visit.objects.create(patient=Patient.objects.create(name="X"), reason="r")
        self.login_as("doctor")
        response = self.client.get(reverse("kiosk:visit-token", args=[visit.token]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse("kiosk:visit-detail", args=[visit.pk]))
