import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class PublicHostHttpsRedirectMiddleware:
    """Redirect plain-HTTP requests on the public host (PUBLIC_BASE_URL) to HTTPS.

    Requests through Cloudflare carry that host name and must use HTTPS.
    Opening the app on the server itself (localhost) keeps working over plain
    HTTP, which is what SECURE_SSL_REDIRECT=false is set for.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public = urlsplit(settings.PUBLIC_BASE_URL)
        host = request.get_host().rsplit(":", 1)[0]
        # Old public domains (REDIRECT_HOSTS) move to the current one, keeping
        # the path, so links and printed ticket QR codes keep working.
        if settings.PUBLIC_BASE_URL and host in settings.REDIRECT_HOSTS:
            return HttpResponsePermanentRedirect(settings.PUBLIC_BASE_URL + request.get_full_path())
        if (
            public.scheme == "https"
            and not request.is_secure()
            and request.get_host().rsplit(":", 1)[0] == public.hostname
        ):
            return HttpResponsePermanentRedirect(f"https://{request.get_host()}{request.get_full_path()}")
        return self.get_response(request)


class ContentSecurityPolicyMiddleware:
    """Send a Content-Security-Policy that only runs the app's own scripts.

    Inline <script> blocks carry a per-request nonce ({{ request.csp_nonce }});
    inline event handlers are not allowed (see static/js/actions.js). Styles
    may stay inline. CSP_REPORT_ONLY=true sends the policy as report-only.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        policy = "; ".join(
            [
                "default-src 'self'",
                f"script-src 'self' 'nonce-{request.csp_nonce}'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: blob:",
                "font-src 'self' data:",
                "connect-src 'self'",
                "media-src 'self' blob:",
                "worker-src 'self' blob:",
                "manifest-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )
        header = "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
        response.headers.setdefault(header, policy)
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(), payment=(), usb=(), bluetooth=(self)")
        return response
