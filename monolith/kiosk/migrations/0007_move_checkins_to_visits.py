"""Give every existing patient a Patient ID and turn each kiosk check-in into a Visit.

Before this, every check-in created a Patient holding the reason for the visit,
with its measurements and queue ticket attached to it. Each such patient gets
one Visit per queue ticket (or one without a ticket), carrying the reason,
the measurements, the queue number and the ticket's QR token, so printed QR
codes keep working.
"""

import secrets

from django.db import migrations
from django.utils import timezone

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
STATUS = {"waiting": "waiting", "in_progress": "in_consultation", "completed": "completed", "cancelled": "cancelled"}


def forwards(apps, schema_editor):
    Patient = apps.get_model("kiosk", "Patient")
    Visit = apps.get_model("kiosk", "Visit")
    Measurement = apps.get_model("kiosk", "Measurement")
    QueueTicket = apps.get_model("kiosk", "QueueTicket")

    used = set(Patient.objects.exclude(patient_id=None).values_list("patient_id", flat=True))
    for patient in Patient.objects.order_by("created_at"):
        if not patient.patient_id:
            while True:
                candidate = "".join(secrets.choice(ALPHABET) for _ in range(5))
                if candidate not in used:
                    break
            used.add(candidate)
            patient.patient_id = candidate
            patient.save(update_fields=["patient_id"])

        reason = patient.symptoms or "(not recorded)"
        tickets = list(QueueTicket.objects.filter(patient=patient).order_by("created_at"))
        visits = []
        for ticket in tickets:
            status = STATUS.get(ticket.status, "waiting")
            if not ticket.is_active and status == "waiting":
                status = "completed"
            visit = Visit.objects.create(
                patient=patient,
                reason=reason,
                token=ticket.qr_code_data,
                queue_date=timezone.localtime(ticket.created_at).date(),
                queue_number=ticket.queue_number,
                status=status,
            )
            Visit.objects.filter(pk=visit.pk).update(created_at=ticket.created_at)
            visits.append(visit)
        if not visits:
            visit = Visit.objects.create(patient=patient, reason=reason, status="completed")
            Visit.objects.filter(pk=visit.pk).update(created_at=patient.created_at)
            visits.append(visit)
        # Measurements belong to the check-in they were taken in: the first visit.
        Measurement.objects.filter(patient=patient, visit=None).update(visit=visits[0])


def backwards(apps, schema_editor):
    Patient = apps.get_model("kiosk", "Patient")
    Visit = apps.get_model("kiosk", "Visit")
    for patient in Patient.objects.all():
        first = Visit.objects.filter(patient=patient).order_by("created_at").first()
        if first:
            patient.symptoms = first.reason
            patient.save(update_fields=["symptoms"])
    Visit.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("kiosk", "0006_patient_registration_and_visits")]

    operations = [migrations.RunPython(forwards, backwards)]
