from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["nurse.example.org", "localhost"], PUBLIC_BASE_URL="https://nurse.example.org")
class HttpsRedirectTest(TestCase):
    def test_public_host_over_http_is_redirected(self):
        response = self.client.get("/accounts/login/?next=/", HTTP_HOST="nurse.example.org")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://nurse.example.org/accounts/login/?next=/")

    def test_public_host_over_https_is_served(self):
        response = self.client.get(reverse("login"), HTTP_HOST="nurse.example.org", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)

    def test_localhost_stays_on_http(self):
        self.assertEqual(self.client.get(reverse("login"), HTTP_HOST="localhost:8010").status_code, 200)
