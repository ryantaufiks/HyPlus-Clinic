"""The four featured services, with example prices the clinic must confirm in the admin."""

from decimal import Decimal

from django.db import migrations

SERVICES = [
    ("Video Consultation", "video-consultation", "bi-camera-video",
     "See a doctor by video from home: assessment, treatment plan and, if appropriate, a prescription, medical certificate or referral.",
     Decimal("49.00"), "per consultation"),
    ("Repeat Prescriptions", "repeat-prescriptions", "bi-capsule",
     "Reorder medication you already take after a quick safety check by our doctor, without another consultation.",
     Decimal("20.00"), "per prescription"),
    ("Fit Notes & Certificates", "fit-notes", "bi-file-earmark-medical",
     "Medical certificates for work or school, signed by the doctor and sent to your phone.",
     Decimal("20.00"), "per certificate"),
    ("Referral Letters", "referral-letters", "bi-envelope-paper",
     "A referral letter to a specialist, hospital or diagnostic centre, written by your doctor.",
     Decimal("25.00"), "per letter"),
]


def add(apps, schema_editor):
    Service = apps.get_model("kiosk", "Service")
    for order, (name, slug, icon, summary, price, unit) in enumerate(SERVICES):
        Service.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "icon": icon, "summary": summary, "price_sgd": price, "price_unit": unit, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("kiosk", "0017_website")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
