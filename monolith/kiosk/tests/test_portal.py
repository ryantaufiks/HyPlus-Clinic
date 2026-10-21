import datetime as dt
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from kiosk.models import Measurement, Patient, PatientSubmission, PrescriptionItem, Visit
from kiosk.portal_views import ensure_portal_user
from kiosk.roles import apply_role

DOB = dt.date(1985, 11, 2)
PASSWORD = "correct-horse-battery"


def staff(role="frontdesk", username="desk"):
    user, created = get_user_model().objects.get_or_create(username=username)
    if created:
        apply_role(user, role)
    return user


@override_settings(PUBLIC_BASE_URL="https://nurse.example.org")
class PortalTest(TestCase):
    def setUp(self):
        cache.clear()
        self.patient = Patient.objects.create(name="Dewi Lestari", phone="0812 3456 7890", date_of_birth=DOB)
        self.visit = Visit.objects.create(
            patient=self.patient, reason="Headache", queue_date=timezone.localdate(), queue_number="A001",
            diagnosis="Tension headache", doctor_notes="PRIVATE NOTE", status=Visit.COMPLETED,
        )
        Measurement.objects.create(patient=self.patient, visit=self.visit, systolic_bp=128, diastolic_bp=82)
        PrescriptionItem.objects.create(visit=self.visit, drug="Paracetamol", dose="500 mg", frequency="3x daily")

    def invite(self):
        self.client.force_login(staff())
        response = self.client.post(reverse("kiosk:patient-portal-invite", args=[self.patient.pk]))
        self.client.logout()
        return re.search(r'value="https://nurse\.example\.org(/portal/setup/[^"]+)"', response.content.decode()).group(1), response

    def activate(self, path, **overrides):
        data = {"date_of_birth": DOB.isoformat(), "new_password1": PASSWORD, "new_password2": PASSWORD, "consent": "on"}
        data.update(overrides)
        return self.client.post(path, data)

    def test_approving_registration_shows_invite_with_whatsapp_to_patient(self):
        submission = PatientSubmission.objects.create(patient=self.patient, visit=self.visit, data={
            "name": "Dewi Lestari", "id_type": "ktp", "id_last4": "1234", "phone": "0812 3456 7890",
            "date_of_birth": DOB.isoformat(), "height_cm": None, "address": "", "has_drug_allergy": False,
            "drug_allergies": "", "medical_history": "", "weight_kg": None,
        })
        self.client.force_login(staff())
        response = self.client.post(reverse("kiosk:submission-review", args=[submission.pk]), {"decision": "approve"})
        self.assertContains(response, "Details approved")
        self.assertContains(response, "https://wa.me/6281234567890?text=")
        self.assertContains(response, "/portal/setup/")
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.user.has_usable_password())

    def test_activation_needs_matching_birth_date_and_consent(self):
        path, _ = self.invite()
        self.assertContains(self.activate(path, date_of_birth="1990-01-01"), "does not match")
        self.assertContains(self.activate(path, consent=""), "You must agree")
        self.assertRedirects(self.activate(path), reverse("portal-login") + "?setup=done", fetch_redirect_response=False)
        self.patient.refresh_from_db()
        self.assertIsNotNone(self.patient.portal_consent_at)
        self.assertContains(self.client.get(path), "no longer valid")  # one-time link

    def test_sign_in_with_patient_id_and_see_own_record(self):
        path, _ = self.invite()
        self.activate(path)
        response = self.client.post(reverse("portal-login"), {"username": self.patient.patient_id.lower(), "password": PASSWORD})
        self.assertRedirects(response, reverse("portal-home"))
        page = self.client.get(reverse("portal-home")).content.decode()
        for text in ["Dewi Lestari", "Tension headache", "Paracetamol", "128/82"]:
            self.assertIn(text, page)
        self.assertNotIn("PRIVATE NOTE", page)
        self.assertEqual(self.client.get(reverse("portal-prescription", args=[self.visit.pk])).status_code, 200)

        other_visit = Visit.objects.create(patient=Patient.objects.create(name="Someone Else"), reason="x")
        self.assertEqual(self.client.get(reverse("portal-prescription", args=[other_visit.pk])).status_code, 404)

    def test_patient_cannot_open_any_staff_page(self):
        user = ensure_portal_user(self.patient)
        user.set_password(PASSWORD)
        user.save()
        self.client.force_login(user)
        staff_urls = [
            reverse("kiosk:dashboard"), reverse("kiosk:dashboard-data"), reverse("kiosk:patient-list"),
            reverse("kiosk:patient-detail", args=[self.patient.pk]), reverse("kiosk:patient-edit", args=[self.patient.pk]),
            reverse("kiosk:visit-detail", args=[self.visit.pk]), reverse("kiosk:prescription-print", args=[self.visit.pk]),
            reverse("kiosk:doctor-queue"), reverse("kiosk:submissions"), reverse("kiosk:qr-scanner"),
            reverse("kiosk:devices"), reverse("kiosk:staff-list"), reverse("kiosk:patient-register"),
        ]
        for url in staff_urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        # Their own ticket QR shows the ticket, not the staff view of the visit.
        self.assertContains(self.client.get(reverse("kiosk:visit-token", args=[self.visit.token])), "Your ticket")
        # Signing in on the staff page takes a patient to the portal, never to ?next=.
        self.client.logout()
        response = self.client.post(reverse("login") + "?next=/patients/", {"username": user.username, "password": PASSWORD})
        self.assertRedirects(response, reverse("portal-home"))

    def test_disable_access(self):
        path, _ = self.invite()
        self.activate(path)
        self.client.force_login(staff())
        self.client.post(reverse("kiosk:patient-portal-disable", args=[self.patient.pk]))
        self.client.logout()
        response = self.client.post(reverse("portal-login"), {"username": self.patient.patient_id, "password": PASSWORD})
        self.assertContains(response, "Incorrect Patient ID or password")

    def test_invite_needs_birth_date_and_role(self):
        no_dob = Patient.objects.create(name="No Dob")
        self.client.force_login(staff())
        response = self.client.post(reverse("kiosk:patient-portal-invite", args=[no_dob.pk]))
        self.assertRedirects(response, reverse("kiosk:patient-detail", args=[no_dob.pk]))
        self.assertIsNone(Patient.objects.get(pk=no_dob.pk).user)
        self.client.force_login(staff("doctor", "dr"))
        self.assertEqual(self.client.post(reverse("kiosk:patient-portal-invite", args=[self.patient.pk])).status_code, 403)

    def test_patient_accounts_are_not_staff_accounts(self):
        user = ensure_portal_user(self.patient)
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="a-long-password-123"))
        self.assertNotContains(self.client.get(reverse("kiosk:staff-list")), user.username)
        self.assertEqual(self.client.get(reverse("kiosk:staff-edit", args=[user.pk])).status_code, 404)
        response = self.client.post(reverse("kiosk:staff-create"), {"first_name": "X", "last_name": "", "username": "patient-zzzzz", "email": "", "role": "nurse", "room": ""})
        self.assertContains(response, "reserved for patient accounts")
