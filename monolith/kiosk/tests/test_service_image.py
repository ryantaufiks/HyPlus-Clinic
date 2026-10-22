import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from kiosk.models import Service

from .test_photos import photo_upload

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class ServiceImageTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="a-long-password-123"))
        self.service = Service.objects.get(slug="video-consultation")
        self.url = reverse("admin:kiosk_service_change", args=[self.service.pk])

    def form_data(self, **overrides):
        s = self.service
        data = {
            "name": s.name, "slug": s.slug, "summary": s.summary, "price_sgd": str(s.price_sgd), "price_unit": s.price_unit,
            "icon": s.icon, "is_featured": "on", "is_bookable": "on", "is_active": "on", "sort_order": s.sort_order,
        }
        data.update(overrides)
        return data

    def test_upload_is_cropped_to_16_10_without_metadata_and_shown_on_the_home_page(self):
        self.client.post(self.url, self.form_data(image=photo_upload(1200, 1200, orientation=6, gps=True)))
        self.service.refresh_from_db()
        stored = Image.open(self.service.image.path)
        self.assertEqual((stored.format, stored.size, len(stored.getexif())), ("JPEG", (960, 600), 0))

        home = self.client.get(reverse("kiosk:landing")).content.decode()
        image_url = reverse("kiosk:service-image", args=[self.service.pk])
        self.assertIn(f'src="{image_url}?v=', home)
        self.client.logout()
        response = self.client.get(image_url)  # public
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/jpeg"))

    def test_replacing_or_clearing_deletes_the_old_file(self):
        self.client.post(self.url, self.form_data(image=photo_upload()))
        self.service.refresh_from_db()
        first = self.service.image.path
        self.client.post(self.url, self.form_data(image=photo_upload(fmt="PNG", name="new.png")))
        self.service.refresh_from_db()
        self.assertFalse(os.path.exists(first))
        second = self.service.image.path
        self.client.post(self.url, self.form_data(**{"image-clear": "on"}))
        self.service.refresh_from_db()
        self.assertFalse(self.service.image)
        self.assertFalse(os.path.exists(second))
        self.assertEqual(self.client.get(reverse("kiosk:service-image", args=[self.service.pk])).status_code, 404)

    def test_rejects_files_that_are_not_images(self):
        response = self.client.post(self.url, self.form_data(image=SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")))
        self.assertContains(response, "Upload a valid image")
        self.service.refresh_from_db()
        self.assertFalse(self.service.image)
