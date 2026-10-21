from django import template
from django.urls import reverse

from kiosk.avatars import color, initials
from kiosk.models import Patient, StaffProfile
from kiosk.roles import patient_of

register = template.Library()


@register.inclusion_tag("kiosk/_avatar.html")
def avatar(subject, size=36):
    """A round profile photo, or the person's initials when they have none.

    `subject` is a Patient or a user (staff member or portal patient).
    """
    if subject is None:
        return {"size": size, "initials": "?", "color": color("?"), "name": ""}
    if isinstance(subject, Patient):
        patient, user = subject, None
    else:
        patient, user = patient_of(subject), subject

    if patient is not None:
        name, key, photo = patient.name, f"patient-{patient.pk}", patient.photo
        url = reverse("kiosk:patient-photo", args=[patient.pk]) if photo else ""
    else:
        name = user.get_full_name() or user.get_username()
        key = f"user-{user.pk}"
        try:
            profile = user.profile
        except StaffProfile.DoesNotExist:
            profile = None
        photo = profile.photo if profile else None
        url = reverse("kiosk:staff-photo", args=[user.pk]) if photo else ""
    if url:
        url += "?v=" + photo.name.rsplit("/", 1)[-1][:12]  # new file name after every upload
    return {"size": size, "url": url, "name": name, "initials": initials(name), "color": color(key)}
