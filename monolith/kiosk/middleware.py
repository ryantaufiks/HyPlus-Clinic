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
