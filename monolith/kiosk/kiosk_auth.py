"""Only registered kiosk screens, or signed-in staff allowed to run the kiosk, may use
the kiosk and device-reading API: they create patients and visits and attach
measurements, so they must not be open to anyone on the internet.
"""

import datetime as dt
import hashlib
import secrets
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator

from .models import KioskDevice
from .roles import can

COOKIE_NAME = "hyplus_kiosk"
COOKIE_MAX_AGE = 400 * 24 * 3600  # browsers cap cookies at 400 days
LAST_SEEN_EVERY = dt.timedelta(minutes=5)


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def register(response, name, user):
    """Make the browser receiving `response` a kiosk."""
    key = secrets.token_urlsafe(32)
    device = KioskDevice.objects.create(name=name, key_hash=_hash(key), created_by=user, last_seen_at=timezone.now())
    response.set_cookie(
        COOKIE_NAME, key, max_age=COOKIE_MAX_AGE, httponly=True, secure=not settings.DEBUG, samesite="Strict"
    )
    return device


def device_of(request):
    """The active kiosk this browser is registered as, or None."""
    key = request.COOKIES.get(COOKIE_NAME)
    if not key:
        return None
    device = KioskDevice.objects.filter(key_hash=_hash(key), is_active=True).first()
    if device and (device.last_seen_at is None or timezone.now() - device.last_seen_at > LAST_SEEN_EVERY):
        KioskDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())
    return device


def kiosk_allowed(request):
    return device_of(request) is not None or can(request.user, "use_kiosk")


def kiosk_required(view):
    """Refuse the request unless it comes from a kiosk (use with method_decorator on class views)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not kiosk_allowed(request):
            return JsonResponse({"error": "This screen is not set up as a kiosk. Ask the clinic staff."}, status=403)
        return view(request, *args, **kwargs)

    return wrapper


kiosk_only = method_decorator(kiosk_required, name="dispatch")
