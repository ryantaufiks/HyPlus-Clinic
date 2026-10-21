import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from kiosk.models import AuditEvent
from kiosk.roles import role_of

User = get_user_model()


@override_settings(PUBLIC_BASE_URL="https://nurse.example.org")
class StaffAccountsTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="a-long-password-123")
        self.client.force_login(self.admin)

    def create(self, **data):
        payload = {"first_name": "Rina", "last_name": "Wulan", "username": "Rina.W", "email": "", "role": "nurse"}
        payload.update(data)
        return self.client.post(reverse("kiosk:staff-create"), payload)

    def link_from(self, response):
        return re.search(r'value="(https://nurse\.example\.org/accounts/setup/[^"]+)"', response.content.decode()).group(1)

    def test_only_administrators(self):
        nurse = User.objects.create_user("nurse", password="a-long-password-123", is_staff=True)
        self.client.force_login(nurse)
        for url in (reverse("kiosk:staff-list"), reverse("kiosk:staff-create"), reverse("kiosk:staff-edit", args=[self.admin.pk])):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_create_account_per_role(self):
        for role, username in (("doctor", "dr.budi"), ("nurse", "rina"), ("frontdesk", "desk"), ("admin", "boss")):
            self.create(username=username, role=role)
            user = User.objects.get(username=username)
            self.assertEqual(role_of(user), role)
            self.assertFalse(user.has_usable_password())
        self.assertTrue(User.objects.get(username="rina").is_staff)
        self.assertFalse(User.objects.get(username="desk").is_staff)
        self.assertEqual(AuditEvent.objects.filter(action="staff.created").count(), 4)

    def test_setup_link_lets_staff_choose_password_once(self):
        response = self.create()
        self.assertContains(response, "Account created")
        link = self.link_from(response)
        path = link.removeprefix("https://nurse.example.org")
        self.client.logout()

        set_password_url = self.client.get(path)["Location"]  # Django hides the token from the URL
        response = self.client.post(set_password_url, {"new_password1": "correct-horse-battery", "new_password2": "correct-horse-battery"})
        self.assertRedirects(response, reverse("login") + "?setup=done", fetch_redirect_response=False)
        self.assertTrue(self.client.login(username="rina.w", password="correct-horse-battery"))

        self.client.logout()
        reused = self.client.get(path, follow=True)
        self.assertContains(reused, "This link is no longer valid")

    def test_weak_password_is_rejected(self):
        path = self.link_from(self.create()).removeprefix("https://nurse.example.org")
        self.client.logout()
        set_password_url = self.client.get(path)["Location"]
        response = self.client.post(set_password_url, {"new_password1": "12345678", "new_password2": "12345678"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.get(username="rina.w").has_usable_password())

    def test_username_rules(self):
        self.assertEqual(self.create(username="no spaces!").status_code, 200)
        self.create(username="rina")
        response = self.create(username="RINA")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="rina").count(), 1)

    def test_change_role(self):
        self.create(username="dr.budi", role="doctor")
        user = User.objects.get(username="dr.budi")
        self.client.post(reverse("kiosk:staff-edit", args=[user.pk]), {"first_name": "Budi", "last_name": "", "username": "dr.budi", "email": "", "role": "frontdesk"})
        user.refresh_from_db()
        self.assertEqual(role_of(user), "frontdesk")
        self.assertFalse(user.groups.exists())

    def test_deactivate_and_protect_self(self):
        self.create(username="rina")
        rina = User.objects.get(username="rina")
        self.client.post(reverse("kiosk:staff-edit", args=[rina.pk]), {"action": "deactivate"})
        rina.refresh_from_db()
        self.assertFalse(rina.is_active)

        self.client.post(reverse("kiosk:staff-edit", args=[self.admin.pk]), {"action": "deactivate"})
        self.client.post(reverse("kiosk:staff-edit", args=[self.admin.pk]), {"first_name": "Admin", "last_name": "", "username": "admin", "email": "", "role": "frontdesk"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_superuser)

    def test_new_setup_link(self):
        self.create(username="rina")
        rina = User.objects.get(username="rina")
        response = self.client.post(reverse("kiosk:staff-edit", args=[rina.pk]), {"action": "setup-link"})
        self.assertContains(response, "New link for")
        self.assertIn("/accounts/setup/", self.link_from(response))
