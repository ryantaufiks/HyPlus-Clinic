import hashlib
import secrets

from kiosk.kiosk_auth import COOKIE_NAME
from kiosk.models import KioskDevice


def as_kiosk(client, name="Test kiosk"):
    """Make the test client a registered kiosk screen."""
    key = secrets.token_urlsafe(16)
    KioskDevice.objects.create(name=name, key_hash=hashlib.sha256(key.encode()).hexdigest())
    client.cookies[COOKIE_NAME] = key
    return client
