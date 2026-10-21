import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from kiosk import queue
from kiosk.models import Patient, StaffProfile, Visit
from kiosk.roles import apply_role

MEDIA = tempfile.mkdtemp()


def jpeg():
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (10, 120, 130)).save(buffer, format="JPEG")
    return ContentFile(buffer.getvalue(), name="face.jpg")


def member(username, role, room="", photo=False, on_duty=True, first_name=""):
    user = get_user_model().objects.create_user(username, first_name=first_name or username.title())
    apply_role(user, role)
    profile = StaffProfile.objects.create(user=user, room=room, on_duty=on_duty)
    if photo:
        profile.photo.save("face.jpg", jpeg(), save=True)
    return user


@override_settings(MEDIA_ROOT=MEDIA)
class DisplayPhotosTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.budi = member("budi", "doctor", room="Room 1", photo=True, first_name="Dr. Budi")
        self.siti = member("siti", "doctor", room="Room 2")
        self.away = member("away", "doctor", room="Room 3", photo=True, on_duty=False)
        self.nurse = member("rina", "nurse", room="Triage", photo=True)

    def test_display_data_has_photo_or_initials(self):
        rooms = {r["room"]: r["face"] for r in self.client.get(reverse("kiosk:display-data")).json()["rooms"]}
        self.assertTrue(rooms["Room 1"]["photo"].startswith(f"/display/photos/{self.budi.pk}/?v="))
        self.assertEqual((rooms["Room 2"]["photo"], rooms["Room 2"]["initials"]), ("", "S"))
        self.assertTrue(rooms["Room 2"]["color"].startswith("#"))

    def test_only_on_duty_doctor_photos_are_public(self):
        ok = self.client.get(reverse("kiosk:display-photo", args=[self.budi.pk]))
        self.assertEqual((ok.status_code, ok["Content-Type"]), (200, "image/jpeg"))
        self.assertIn("public", ok["Cache-Control"])
        for user in (self.away, self.nurse, self.siti):  # off duty, not a doctor, no photo
            self.assertEqual(self.client.get(reverse("kiosk:display-photo", args=[user.pk])).status_code, 404, user)

    def test_off_duty_doctor_with_patient_still_shown(self):
        visit = Visit.objects.create(patient=Patient.objects.create(name="X"), reason="r", queue_date=timezone.localdate(), queue_number="A001")
        queue.call(visit, self.away)  # calling puts them on duty again
        StaffProfile.objects.filter(user=self.away).update(on_duty=False)
        self.assertEqual(self.client.get(reverse("kiosk:display-photo", args=[self.away.pk])).status_code, 200)

    def test_called_patient_shows_doctor_face(self):
        visit = Visit.objects.create(patient=Patient.objects.create(name="X"), reason="r", queue_date=timezone.localdate(), queue_number="A001")
        queue.call(visit, self.budi)
        called = self.client.get(reverse("kiosk:display-data")).json()["called"][0]
        self.assertEqual((called["queue_number"], called["doctor"]), ("A001", "Dr. Budi"))
        self.assertTrue(called["face"]["photo"])
