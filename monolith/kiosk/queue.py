"""Queue flow: waiting -> called -> in consultation -> completed.

All status changes go through these functions so the doctor's screen, the
access-control tablet and the waiting-room TV always agree.
"""

import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AuditEvent, StaffProfile, Visit
from .roles import is_doctor
from .vitals import bp_category


class QueueError(Exception):
    """A queue action that is not allowed in the visit's current state."""


def todays_queue():
    return Visit.objects.filter(queue_date=timezone.localdate()).exclude(queue_number="")


def waiting_in_order(doctor=None):
    """Waiting visits in calling order: critical blood pressure first, then queue number.

    With `doctor`, only the visits in that doctor's line: patients who chose
    them, patients who chose the first available doctor, and patients whose
    chosen doctor is no longer on duty (so nobody is left stranded).
    """
    visits = todays_queue().filter(status=Visit.WAITING)
    if doctor is not None:
        on_duty = [d.pk for d, _ in doctors_on_duty()]
        visits = visits.filter(
            Q(requested_doctor=doctor) | Q(requested_doctor__isnull=True) | ~Q(requested_doctor__in=on_duty)
        )
    visits = list(visits.select_related("requested_doctor").prefetch_related("measurements"))

    def urgent(visit):
        bp = next((m for m in visit.measurements.all() if m.systolic_bp is not None and m.diastolic_bp is not None), None)
        category = bp_category(bp.systolic_bp, bp.diastolic_bp) if bp else None
        return category is not None and category.status == "critical"

    return sorted(visits, key=lambda v: (not urgent(v), v.queue_number))


def chosen_doctor(visit, on_duty=None):
    """The doctor whose line this visit is in, or None for the first available doctor."""
    if visit.requested_doctor_id is None:
        return None
    if on_duty is None:
        on_duty = {d.pk for d, _ in doctors_on_duty()}
    return visit.requested_doctor if visit.requested_doctor_id in on_duty else None


def doctors_on_duty():
    """(doctor, room) for every active doctor who is on duty and has a room, by room name."""
    profiles = StaffProfile.objects.filter(on_duty=True, user__is_active=True).exclude(room="").select_related("user")
    pairs = [(p.user, p.room) for p in profiles if is_doctor(p.user)]
    return sorted(pairs, key=lambda pair: (_natural(pair[1]), pair[0].get_full_name()))


def _natural(text):
    """'Room 2' before 'Room 10'."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def set_on_duty(user, on_duty):
    StaffProfile.objects.update_or_create(user=user, defaults={"on_duty": on_duty})


def call(visit, doctor):
    """Call a waiting patient to the doctor's room (or call them again)."""
    set_on_duty(doctor, True)
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
    """Call the next patient in this doctor's line, or return None when nobody is waiting."""
    for candidate in waiting_in_order(doctor):
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


CANCEL_REASONS = ["No-show", "Patient left", "Duplicate ticket", "Registered by mistake"]


def cancel(visit, actor, reason):
    """Take a visit out of the queue. The visit and its vitals are kept."""
    reason = " ".join(str(reason or "").split())
    if len(reason) < 3:
        raise QueueError("Enter the reason for cancelling.")
    with transaction.atomic():
        visit = Visit.objects.select_for_update().get(pk=visit.pk)
        if visit.status not in (Visit.WAITING, Visit.CALLED, Visit.IN_CONSULTATION):
            raise QueueError(f"{visit.queue_number or 'This visit'} is already {visit.get_status_display().lower()}.")
        visit.status = Visit.CANCELLED
        visit.cancel_reason = reason[:200]
        visit.cancelled_by = actor
        visit.cancelled_at = timezone.now()
        visit.save(update_fields=["status", "cancel_reason", "cancelled_by", "cancelled_at"])
        AuditEvent.record(actor, "queue.cancelled", visit=visit, reason=visit.cancel_reason)
    return visit


def position(visit):
    """How many waiting patients will be called before this one (None if not waiting).

    A patient who chose a doctor counts only that doctor's line.
    """
    if visit.status != Visit.WAITING:
        return None
    order = [v.pk for v in waiting_in_order(chosen_doctor(visit))]
    return order.index(visit.pk) if visit.pk in order else None

