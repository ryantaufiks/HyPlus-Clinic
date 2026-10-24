from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from kiosk.roles import apply_role


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="a-long-password-123")
    apply_role(user, role)
    return user


class SettingsHomeTest(TestCase):
    url = reverse("kiosk:settings")

    def test_admin_sees_every_module(self):
        self.client.force_login(user_with_role("ada", "admin"))
        page = self.client.get(self.url)
        for text in ["Staff accounts", "Services &amp; prices", "Medical devices", "Kiosk screens",
                     "AI &amp; system settings", "Audit log", "Staff attendance", "Coming soon"]:
            self.assertContains(page, text)
        self.assertContains(page, "OpenAI key not set")

    def test_nurse_sees_only_the_modules_they_can_open(self):
        self.client.force_login(user_with_role("nina", "nurse"))
        page = self.client.get(self.url)
        self.assertContains(page, "Medical devices")
        self.assertContains(page, "Patient reviews")
        self.assertNotContains(page, "Staff accounts")
        self.assertNotContains(page, "AI &amp; system settings")

    def test_doctor_and_front_desk_are_refused(self):
        for name, role in [("doc", "doctor"), ("fd", "frontdesk")]:
            self.client.force_login(user_with_role(name, role))
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_settings_link_replaces_the_menu(self):
        self.client.force_login(user_with_role("ada", "admin"))
        page = self.client.get(reverse("kiosk:dashboard"))
        self.assertContains(page, f'href="{self.url}"')
