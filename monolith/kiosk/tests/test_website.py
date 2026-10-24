import datetime as dt

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk.models import BookingRequest, Patient, Review, Service, Visit
from kiosk.portal_views import ensure_portal_user

from .test_queue import user_with_role


def booking_data(**overrides):
    data = {
        "service": Service.objects.get(slug="video-consultation").pk,
        "preferred_doctor": "",
        "preferred_date": (timezone.localdate() + dt.timedelta(days=2)).isoformat(),
        "preferred_time": "morning",
        "name": "Dewi Lestari",
        "phone": "+65 8123 4567",
        "email": "",
        "notes": "Cough for a week",
        "consent": "on",
        "website": "",
    }
    data.update(overrides)
    return data


class LandingTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_home_page_lists_services_with_sgd_prices_and_kiosk_moved(self):
        response = self.client.get(reverse("kiosk:landing"))
        self.assertEqual(reverse("kiosk:landing"), "/demo/")
        for text in ["Video Consultation", "Repeat Prescriptions", "Fit Notes &amp; Certificates", "Referral Letters", "SGD 49", "Example price", "How it works"]:
            self.assertContains(response, text)
        self.assertContains(response, "Reviews from our first patients are on their way")  # none approved yet
        self.assertNotContains(response, "Preview · sample reviews")
        self.assertEqual(reverse("kiosk:home"), "/kiosk/")
        self.assertContains(self.client.get("/kiosk/"), "Check-in")

        Service.objects.update(price_confirmed=True)
        self.assertNotContains(self.client.get(reverse("kiosk:landing")), "Example price")

    def test_shows_doctors_on_duty(self):
        user_with_role("budi", "doctor", room="Room 1")
        self.assertContains(self.client.get(reverse("kiosk:landing")), "Room 1")


class BookingTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_booking_request_is_saved_for_staff(self):
        doctor = user_with_role("budi", "doctor", room="Room 1")
        response = self.client.post(reverse("kiosk:book"), booking_data(preferred_doctor=doctor.pk))
        self.assertContains(response, "Booking request sent")
        booking = BookingRequest.objects.get()
        self.assertEqual((booking.status, booking.preferred_doctor, booking.phone), (BookingRequest.NEW, doctor, "+65 8123 4567"))
        self.assertIsNotNone(booking.consent_at)

        desk = user_with_role("desk", "frontdesk")
        self.client.force_login(desk)
        page = self.client.get(reverse("kiosk:bookings"))
        self.assertContains(page, "Dewi Lestari")
        self.assertContains(page, "https://wa.me/6581234567?text=")
        self.client.post(reverse("kiosk:booking-update", args=[booking.pk]), {"status": "confirmed", "staff_note": "10:30"})
        booking.refresh_from_db()
        self.assertEqual((booking.status, booking.staff_note, booking.handled_by), ("confirmed", "10:30", desk))

    def test_validation_and_bots(self):
        response = self.client.post(reverse("kiosk:book"), booking_data(preferred_date="2000-01-01", consent=""))
        self.assertContains(response, "Choose today or a later date")
        self.assertContains(response, "This field is required")
        far = (timezone.localdate() + dt.timedelta(days=90)).isoformat()
        self.assertContains(self.client.post(reverse("kiosk:book"), booking_data(preferred_date=far)), "60 days ahead")
        self.client.post(reverse("kiosk:book"), booking_data(website="http://spam.example"))
        self.assertFalse(BookingRequest.objects.exists())

    def test_only_front_office_staff_handle_bookings(self):
        self.client.force_login(user_with_role("budi", "doctor"))
        self.assertEqual(self.client.get(reverse("kiosk:bookings")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("kiosk:bookings")).status_code, 302)


class ReviewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.patient = Patient.objects.create(name="Thomas Kurniawan", date_of_birth=dt.date(1990, 1, 1))
        self.visit = Visit.objects.create(patient=self.patient, reason="Flu", status=Visit.COMPLETED)
        self.client.force_login(ensure_portal_user(self.patient))

    def review(self, visit=None, **data):
        return self.client.post(reverse("portal-review", args=[(visit or self.visit).pk]), {"rating": 5, "comment": "Quick and friendly, thank you!", **data})

    def test_patient_reviews_completed_visit_once_and_staff_approve(self):
        self.review()
        self.review(comment="A second review for the same visit")
        review = Review.objects.get()
        self.assertEqual((review.rating, review.status, review.display_name), (5, Review.PENDING, "Thomas K."))
        self.assertNotContains(self.client.get(reverse("kiosk:landing")), "Quick and friendly")

        nurse = user_with_role("nurse", "nurse")
        self.client.force_login(nurse)
        self.client.post(reverse("kiosk:reviews"), {"review": review.pk, "decision": "approved"})
        home = self.client.get(reverse("kiosk:landing"))
        self.assertContains(home, "Quick and friendly")
        self.assertContains(home, "Thomas K.")
        self.assertNotContains(home, "Kurniawan")

    def test_cannot_review_open_or_other_patients_visits(self):
        open_visit = Visit.objects.create(patient=self.patient, reason="x", status=Visit.WAITING)
        self.assertEqual(self.review(open_visit).status_code, 404)
        other = Visit.objects.create(patient=Patient.objects.create(name="Other"), reason="x", status=Visit.COMPLETED)
        self.assertEqual(self.review(other).status_code, 404)
        self.review(rating=9)
        self.assertFalse(Review.objects.exists())


class BookingChoicesTest(TestCase):
    def test_booking_only_accepts_listed_doctors_and_services(self):
        cache.clear()
        nurse = user_with_role("nurse", "nurse")
        response = self.client.post(reverse("kiosk:book"), booking_data(preferred_doctor=nurse.pk))
        self.assertContains(response, "Select a valid choice")
        Service.objects.filter(slug="video-consultation").update(is_active=False)
        self.assertContains(self.client.post(reverse("kiosk:book"), booking_data()), "Select a valid choice")
        self.assertFalse(BookingRequest.objects.exists())


class ReviewPreviewTest(TestCase):
    def test_sample_reviews_only_for_staff_and_only_until_real_ones_exist(self):
        cache.clear()
        self.assertNotContains(self.client.get(reverse("kiosk:landing")), "Sarah L.")  # never shown to the public
        self.client.force_login(user_with_role("desk", "frontdesk"))
        page = self.client.get(reverse("kiosk:landing"))
        self.assertContains(page, "Preview · sample reviews, visible to staff only")
        self.assertContains(page, "Sarah L.")

        patient = Patient.objects.create(name="Thomas Kurniawan")
        visit = Visit.objects.create(patient=patient, reason="Flu", status=Visit.COMPLETED)
        Review.objects.create(visit=visit, patient=patient, rating=5, comment="Real review from a real visit.", status=Review.APPROVED)
        page = self.client.get(reverse("kiosk:landing"))
        self.assertContains(page, "Real review from a real visit.")
        self.assertNotContains(page, "Sarah L.")
        self.assertNotContains(page, "Preview · sample reviews")


class PlatformPageTest(TestCase):
    def setUp(self):
        cache.clear()

    def contact(self, **overrides):
        data = {"name": "Andi Wijaya", "email": "andi@example.com", "phone": "", "organisation": "Klinik Sehat",
                "interest": "white_label", "message": "We run three clinics and want our own brand.", "consent": "on", "website": ""}
        data.update(overrides)
        return self.client.post(reverse("kiosk:platform"), data)

    def test_platform_page_sells_the_platform_and_links_the_demo(self):
        page = self.client.get("/")
        for text in ["More time for patients", "Secure video consultation", "Staff attendance", "Pulse oximeter", "Uric acid meter", "White label",
                     "CTO / Founding engineer", "Contact us", reverse("kiosk:landing")]:
            self.assertContains(page, text)
        self.assertNotContains(page, "SGD")  # no clinic prices on the platform page
        self.assertContains(page, "Works with the brands you already use")
        self.assertContains(page, 'aria-label="Hikvision"')
        self.assertContains(page, "no partnership or endorsement is implied")
        demo = self.client.get(reverse("kiosk:landing"))
        self.assertContains(demo, "Demo clinic")
        self.assertContains(demo, "SGD 49")

    def test_contact_form_saves_an_inquiry(self):
        from kiosk.models import PartnerInquiry

        self.assertContains(self.contact(), "Thank you, we")
        inquiry = PartnerInquiry.objects.get()
        self.assertEqual((inquiry.interest, inquiry.organisation, inquiry.status), ("white_label", "Klinik Sehat", "new"))
        self.assertContains(self.contact(message="hi"), "Please tell us a little more")
        self.contact(website="http://spam.example")  # bots: quietly dropped
        self.assertEqual(PartnerInquiry.objects.count(), 1)
        self.assertContains(self.client.get("/?interest=cto"), '<option value="cto" selected>')
