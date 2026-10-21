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


class ContentSecurityPolicyTest(TestCase):
    def test_scripts_need_the_request_nonce(self):
        response = self.client.get(reverse("login"))  # base.html has inline scripts
        policy = response["Content-Security-Policy"]
        self.assertIn("object-src 'none'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertNotIn("'unsafe-inline' 'unsafe-eval'", policy)
        nonce = policy.split("'nonce-")[1].split("'")[0]
        self.assertIn(f'<script nonce="{nonce}">', response.content.decode())
        self.assertNotEqual(nonce, self.client.get("/").headers["Content-Security-Policy"].split("'nonce-")[1].split("'")[0])

    def test_templates_have_no_inline_event_handlers(self):
        import pathlib
        import re

        templates = pathlib.Path(__file__).resolve().parents[1] / "templates"
        offenders = [
            f"{path.name}: {m.group(0)}"
            for path in templates.rglob("*.html")
            for m in re.finditer(r"\son[a-z]+=\"", path.read_text())
        ]
        self.assertEqual(offenders, [])
