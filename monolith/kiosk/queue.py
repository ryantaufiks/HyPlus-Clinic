"""Queue flow: waiting -> called -> in consultation -> completed.

All status changes go through these functions so the doctor's screen, the
access-control tablet and the waiting-room TV always agree.
"""

from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, StaffProfile, Visit
from .vitals import bp_category


class QueueError(Exception):
    """A queue action that is not allowed in the visit's current state."""


def todays_queue():
    return Visit.objects.filter(queue_date=timezone.localdate()).exclude(queue_number="")


def waiting_in_order():
    """Waiting visits in calling order: critical blood pressure first, then queue number."""
    visits = list(todays_queue().filter(status=Visit.WAITING).prefetch_related("measurements"))

    def urgent(visit):
        bp = next((m for m in visit.measurements.all() if m.systolic_bp is not None and m.diastolic_bp is not None), None)
        category = bp_category(bp.systolic_bp, bp.diastolic_bp) if bp else None
        return category is not None and category.status == "critical"

    return sorted(visits, key=lambda v: (not urgent(v), v.queue_number))


def call(visit, doctor):
    """Call a waiting patient to the doctor's room (or call them again)."""
    with transaction.atomic():
        visit = Visit.objects.select_for_update().get(pk=visit.pk)
        if visit.status not in (Visit.WAITING, Visit.CALLED):
            raise QueueError(f"{visit.queue_number} is {visit.get_status_display().lower()} and cannot be called.")
        recall = visit.status == Visit.CALLED
        visit.status = Visit.CALLED
        visit.doctor = doctor
        visit.room = StaffProfile.room_for(doctor)
        visit.called_at = timezone.now()
        visit.call_count += 1
        visit.save(update_fields=["status", "doctor", "room", "called_at", "call_count"])
        AuditEvent.record(doctor, "queue.recalled" if recall else "queue.called", visit=visit, room=visit.room)
    return visit


def call_next(doctor):
    """Call the next waiting patient, or return None when nobody is waiting."""
    for candidate in waiting_in_order():
        try:
            return call(candidate, doctor)
        except QueueError:
            continue  # another doctor called them a moment ago
    return None


def admit(token, actor):
    """The patient scanned their ticket at the consulting-room door."""
    with transaction.atomic():
        visit = Visit.objects.select_for_update().select_related("patient").filter(token=token).first()
        if visit is None:
            raise QueueError("This is not an AIVIN ticket.")
        if visit.queue_date != timezone.localdate():
            raise QueueError("This ticket is not for today.")
        if visit.status == Visit.WAITING:
            raise QueueError(f"{visit.queue_number} has not been called yet. Please wait for your number on the screen.")
        if visit.status == Visit.IN_CONSULTATION:
            return visit  # scanned twice; already inside
        if visit.status != Visit.CALLED:
            raise QueueError(f"{visit.queue_number} is {visit.get_status_display().lower()}.")
        visit.status = Visit.IN_CONSULTATION
        visit.started_at = timezone.now()
        visit.save(update_fields=["status", "started_at"])
        AuditEvent.record(actor, "queue.admitted", visit=visit, room=visit.room)
    return visit


def complete(visit, doctor):
    visit.status = Visit.COMPLETED
    visit.completed_at = timezone.now()
    visit.save(update_fields=["status", "completed_at"])


def no_show(visit, actor):
    with transaction.atomic():
        visit = Visit.objects.select_for_update().get(pk=visit.pk)
        if visit.status not in (Visit.WAITING, Visit.CALLED):
            raise QueueError(f"{visit.queue_number} is already {visit.get_status_display().lower()}.")
        visit.status = Visit.CANCELLED
        visit.save(update_fields=["status"])
        AuditEvent.record(actor, "queue.no_show", visit=visit)
    return visit


def position(visit):
    """How many waiting patients will be called before this one (None if not waiting)."""
    if visit.status != Visit.WAITING:
        return None
    order = [v.pk for v in waiting_in_order()]
    return order.index(visit.pk) if visit.pk in order else None
