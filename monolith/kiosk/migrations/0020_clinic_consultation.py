"""The in-person consultation, the service behind the online queue (example price)."""

from decimal import Decimal

from django.db import migrations


def add(apps, schema_editor):
    Service = apps.get_model("kiosk", "Service")
    Service.objects.get_or_create(
        slug="clinic-consultation",
        defaults={
            "name": "Clinic Consultation",
            "icon": "bi-hospital",
            "summary": "See a doctor in person. Take a queue number online or at the kiosk; your vitals are measured before you go in.",
            "price_sgd": Decimal("35.00"),
            "price_unit": "per consultation",
            "sort_order": 0,
        },
    )
    # Show it first.
    Service.objects.exclude(slug="clinic-consultation").filter(sort_order__lt=10).update(sort_order=10)


class Migration(migrations.Migration):
    dependencies = [("kiosk", "0019_online_queue")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
