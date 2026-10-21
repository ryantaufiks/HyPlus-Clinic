"""Profile photos: processing uploads and the initials shown when there is none."""

import hashlib
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Muted tones that all keep white initials readable (contrast >= 4.5:1).
COLORS = ["#0b7a83", "#2a62b8", "#7a4fc4", "#b4436c", "#9a5412", "#2f7d32", "#5c6b7a"]
TITLES = {"dr", "dr.", "drg", "drg.", "prof", "prof.", "mr", "mr.", "mrs", "mrs.", "ms", "ms."}


def process_photo(upload):
    """A square 256×256 JPEG of the upload: rotated upright, centre-cropped, no metadata."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("The photo is larger than 5 MB.")
    try:
        image = Image.open(upload)
        image.verify()  # rejects truncated or fake images
        upload.seek(0)
        image = Image.open(upload)
    except (UnidentifiedImageError, OSError):
        raise ValidationError("That file is not a photo we can read. Use a JPG, PNG or WebP image.")
    if image.format not in ALLOWED_FORMATS:
        raise ValidationError("Use a JPG, PNG or WebP image.")
    if image.width * image.height > 40_000_000:
        raise ValidationError("The photo is too large.")

    image = ImageOps.exif_transpose(image)  # phones store rotation in EXIF
    image = ImageOps.fit(image.convert("RGB"), (SIZE, SIZE), Image.LANCZOS)
    out = BytesIO()
    image.save(out, format="JPEG", quality=85, optimize=True)  # a fresh file: EXIF (incl. GPS) is dropped
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


def replace_photo(obj, upload):
    """Process `upload` and store it as obj.photo, deleting the previous file."""
    content = process_photo(upload)
    old = obj.photo.name if obj.photo else None
    obj.photo.save(content.name, content, save=True)
    if old:
        obj.photo.storage.delete(old)


def remove_photo(obj):
    if obj.photo:
        obj.photo.delete(save=True)


def initials(name):
    words = [w for w in (name or "").replace(",", " ").split() if w.lower() not in TITLES]
    if not words:
        return "?"
    letters = words[0][0] + (words[-1][0] if len(words) > 1 else "")
    return letters.upper()


def color(key):
    digest = hashlib.sha1(str(key).encode()).digest()
    return COLORS[digest[0] % len(COLORS)]
