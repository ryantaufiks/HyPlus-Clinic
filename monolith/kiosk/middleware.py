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
        if (
            public.scheme == "https"
            and not request.is_secure()
            and request.get_host().rsplit(":", 1)[0] == public.hostname
        ):
            return HttpResponsePermanentRedirect(f"https://{request.get_host()}{request.get_full_path()}")
        return self.get_response(request)
