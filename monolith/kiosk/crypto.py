"""Symmetric encryption for secrets stored in the database."""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token):
    """Return the plaintext, or "" if the token is empty or was encrypted with another key."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
