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


@override_settings(
    ALLOWED_HOSTS=["old.example.org", "new.example.org"], PUBLIC_BASE_URL="https://new.example.org", REDIRECT_HOSTS=["old.example.org"]
)
class OldDomainRedirectTest(TestCase):
    def test_old_domain_moves_to_new_one_keeping_the_path(self):
        response = self.client.get("/v/abc/?new=1", HTTP_HOST="old.example.org", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual((response.status_code, response["Location"]), (301, "https://new.example.org/v/abc/?new=1"))
        self.assertEqual(self.client.get(reverse("login"), HTTP_HOST="new.example.org", HTTP_X_FORWARDED_PROTO="https").status_code, 200)
