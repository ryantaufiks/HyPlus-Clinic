import datetime as dt
import os
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from kiosk.avatars import initials
from kiosk.models import Patient, StaffProfile
from kiosk.portal_views import ensure_portal_user
from kiosk.roles import apply_role

MEDIA = tempfile.mkdtemp()


def photo_upload(width=800, height=600, orientation=None, gps=False, fmt="JPEG", name="me.jpg"):
    image = Image.new("RGB", (width, height), (200, 30, 30))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if gps:
        exif[0x8825] = {1: "S", 2: (6.0, 12.0, 30.0)}  # GPSInfo
    buffer = BytesIO()
    image.save(buffer, format=fmt, **({"exif": exif.tobytes()} if fmt == "JPEG" else {}))
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


@override_settings(MEDIA_ROOT=MEDIA)
class PhotoTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.doctor = get_user_model().objects.create_user("budi", password="a-long-password-123", first_name="Dr. Budi", last_name="Santoso")
        apply_role(self.doctor, "doctor")
        self.client.force_login(self.doctor)

    def upload(self, file):
        return self.client.post(reverse("kiosk:my-profile"), {"photo": file})

    def test_upload_is_square_upright_and_stripped(self):
        self.upload(photo_upload(800, 600, orientation=6, gps=True))
        profile = StaffProfile.objects.get(user=self.doctor)
        stored = Image.open(profile.photo.path)
        self.assertEqual((stored.format, stored.size), ("JPEG", (256, 256)))
        self.assertEqual(len(stored.getexif()), 0)  # no orientation, no GPS

    def test_rejects_non_images_and_large_files(self):
        response = self.upload(SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg"))
        self.assertFalse(StaffProfile.objects.filter(user=self.doctor).exclude(photo="").exists())
        self.assertContains(self.client.get(reverse("kiosk:my-profile")), "not a photo we can read")
        big = SimpleUploadedFile("big.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        self.upload(big)
        self.assertContains(self.client.get(reverse("kiosk:my-profile")), "larger than 5 MB")

    def test_replace_deletes_old_file_and_remove(self):
        self.upload(photo_upload())
        first = StaffProfile.objects.get(user=self.doctor).photo
        first_path = first.path
        self.upload(photo_upload(fmt="PNG", name="new.png"))
        profile = StaffProfile.objects.get(user=self.doctor)
        self.assertNotEqual(profile.photo.name, first.name)
        self.assertTrue(os.path.exists(profile.photo.path))
        self.assertFalse(os.path.exists(first_path))
        self.client.post(reverse("kiosk:my-profile"), {"action": "remove"})
        self.assertFalse(StaffProfile.objects.get(user=self.doctor).photo)

    def test_patient_photo_access(self):
        patient = Patient.objects.create(name="Dewi Lestari", date_of_birth=dt.date(1985, 1, 1))
        user = ensure_portal_user(patient)
        self.client.force_login(user)
        self.client.post(reverse("portal-photo"), {"photo": photo_upload()})
        patient.refresh_from_db()
        self.assertTrue(patient.photo)
        url = reverse("kiosk:patient-photo", args=[patient.pk])
        self.assertEqual(self.client.get(url).status_code, 200)  # own photo

        other = ensure_portal_user(Patient.objects.create(name="Someone Else"))
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)  # not other patients

        self.client.force_login(self.doctor)
        response = self.client.get(url)
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/jpeg"))
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # never public

    def test_staff_photo_visible_to_signed_in_users_only(self):
        self.upload(photo_upload())
        url = reverse("kiosk:staff-photo", args=[self.doctor.pk])
        patient_user = ensure_portal_user(Patient.objects.create(name="Dewi"))
        self.client.force_login(patient_user)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_initials_fallback(self):
        self.assertEqual(initials("Dr. Budi Santoso"), "BS")
        self.assertEqual(initials("ryan"), "R")
        self.assertEqual(initials(""), "?")
        html = Template("{% load avatars %}{% avatar u 40 %}").render(Context({"u": self.doctor}))
        self.assertIn(">BS</span>", html)
        self.upload(photo_upload())
        html = Template("{% load avatars %}{% avatar u 40 %}").render(Context({"u": get_user_model().objects.get(pk=self.doctor.pk)}))
        self.assertIn(f'src="/photos/staff/{self.doctor.pk}/?v=', html)
