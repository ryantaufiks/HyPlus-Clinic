"""Figures for the dashboard: what the desk needs right now, and how the clinic did over a period.

Times come from the visit's own timestamps:
  wait          checked_in_at -> called_at   (time in the waiting room)
  consultation  started_at -> completed_at   (time with the doctor)
A patient called more than once keeps the time of the latest call, so a recall
counts as part of the wait.
"""

import datetime as dt
from collections import Counter, defaultdict
from statistics import mean

from django.urls import reverse
from django.utils import timezone

from .models import Measurement, Visit
from .queue import chosen_doctor, doctors_on_duty, todays_queue, waiting_in_order
from .vitals import BP_CATEGORIES, bp_category

PERIODS = (7, 30, 90)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
QUEUE_ROWS = 60  # rows sent to the dashboard; the counts are never capped


def _minutes(start, end):
    if not start or not end or end < start:
        return None
    return (end - start).total_seconds() / 60


def _avg(values):
    values = [v for v in values if v is not None]
    return round(mean(values), 1) if values else None


def _name(user):
    return (user.get_full_name() or user.get_username()) if user else ""


def _bp_of(visit):
    """The visit's latest blood pressure reading (measurements are prefetched, newest first)."""
    return next((m for m in visit.measurements.all() if m.systolic_bp is not None and m.diastolic_bp is not None), None)


# --- Today ----------------------------------------------------------------------------------------


def today_overview():
    now = timezone.now()
    on_duty = doctors_on_duty()
    on_duty_ids = {d.pk for d, _ in on_duty}
    visits = list(
        todays_queue()
        .select_related("patient", "doctor", "requested_doctor")
        .prefetch_related("measurements")
    )
    by_status = defaultdict(list)
    for v in visits:
        key = "not_arrived" if v.status == Visit.WAITING and not v.is_checked_in else v.status
        by_status[key].append(v)

    waiting = waiting_in_order()  # arrived, in calling order: urgent first
    rows = []
    for group, status_label in (
        (by_status[Visit.CALLED], "Called"),
        (by_status[Visit.IN_CONSULTATION], "In consultation"),
        (waiting, "Waiting"),
        (sorted(by_status["not_arrived"], key=lambda v: v.queue_number), "Not arrived"),
    ):
        for v in group:
            bp = _bp_of(v)
            category = bp_category(bp.systolic_bp, bp.diastolic_bp) if bp else None
            if v.doctor_id and v.status != Visit.WAITING:
                doctor = _name(v.doctor)
            else:
                chosen = chosen_doctor(v, on_duty_ids)
                doctor = _name(chosen) if chosen else "First available"
            rows.append({
                "queue_number": v.queue_number,
                "patient": v.patient.name,
                "status": status_label,
                "source": v.get_source_display(),
                "doctor": doctor,
                "room": v.room if v.status != Visit.WAITING else "",
                "checked_in_at": v.checked_in_at.isoformat() if v.checked_in_at else None,
                "called_at": v.called_at.isoformat() if v.called_at else None,
                "started_at": v.started_at.isoformat() if v.started_at else None,
                "bp": f"{bp.systolic_bp}/{bp.diastolic_bp}" if bp else None,
                "pulse": bp.heart_rate_bpm if bp else None,
                "category": {"label": category.label, "status": category.status, "icon": category.icon} if category else None,
                "urgent": status_label == "Waiting" and category is not None and category.status == "critical",
                "url": reverse("kiosk:visit-detail", args=[v.pk]),
            })

    waits_now = [(_minutes(v.checked_in_at, now), v.queue_number) for v in waiting]
    longest = max(waits_now, default=(None, ""))
    avg_wait = _avg(_minutes(v.checked_in_at, v.called_at) for v in visits if v.called_at)

    doctors = []
    for doctor, room in on_duty:
        serving = next((v for v in by_status[Visit.IN_CONSULTATION] + by_status[Visit.CALLED] if v.doctor_id == doctor.pk), None)
        doctors.append({
            "name": _name(doctor),
            "room": room,
            "serving": serving.queue_number if serving else None,
            "serving_status": ("In consultation" if serving.status == Visit.IN_CONSULTATION else "Called") if serving else None,
            "in_line": len(waiting_in_order(doctor)),
            "seen_today": sum(1 for v in by_status[Visit.COMPLETED] if v.doctor_id == doctor.pk),
        })

    return {
        "kpis": {
            "waiting": len(waiting),
            "not_arrived": len(by_status["not_arrived"]),
            "longest_wait_min": round(longest[0]) if longest[0] is not None else None,
            "longest_wait_ticket": longest[1],
            "avg_wait_min": avg_wait,
            "urgent_waiting": sum(1 for r in rows if r["urgent"]),
            "checked_in": sum(1 for v in visits if v.is_checked_in),
            "completed": len(by_status[Visit.COMPLETED]),
            "cancelled": len(by_status[Visit.CANCELLED]),
            "with_doctor": len(by_status[Visit.CALLED]) + len(by_status[Visit.IN_CONSULTATION]),
        },
        "queue": rows[:QUEUE_ROWS],
        "queue_total": len(rows),
        "doctors": doctors,
    }


# --- Period report --------------------------------------------------------------------------------


def period_report(days):
    """How the clinic did over the last `days` days, today included."""
    today = timezone.localdate()
    start = today - dt.timedelta(days=days - 1)
    visits = list(
        Visit.objects.filter(queue_date__gte=start, queue_date__lte=today)
        .exclude(queue_number="")
        .select_related("doctor")
        .only("patient_id", "queue_date", "status", "source", "cancel_reason", "checked_in_at", "called_at",
              "started_at", "completed_at", "doctor__first_name", "doctor__last_name", "doctor__username")
    )

    # Visits per day, split by outcome. Past days still open were never seen.
    day_list = [start + dt.timedelta(days=i) for i in range(days)]
    per_day = {d: Counter() for d in day_list}
    waits, consults = defaultdict(list), defaultdict(list)
    heat = Counter()
    for v in visits:
        if v.status == Visit.COMPLETED:
            outcome = "completed"
        elif v.status == Visit.CANCELLED:
            outcome = "no_show" if v.cancel_reason == "No-show" else "cancelled"
        elif v.queue_date < today:
            outcome = "no_show"
        else:
            outcome = "open"
        per_day[v.queue_date][outcome] += 1
        waits[v.queue_date].append(_minutes(v.checked_in_at, v.called_at))
        consults[v.queue_date].append(_minutes(v.started_at, v.completed_at))
        if v.checked_in_at:
            local = timezone.localtime(v.checked_in_at)
            heat[(local.weekday(), local.hour)] += 1

    daily = [{
        "date": d.isoformat(),
        "completed": per_day[d]["completed"],
        "cancelled": per_day[d]["cancelled"],
        "no_show": per_day[d]["no_show"],
        "open": per_day[d]["open"],
        "avg_wait_min": _avg(waits[d]),
        "avg_consult_min": _avg(consults[d]),
    } for d in day_list]

    hours = sorted({h for _, h in heat}) or list(range(8, 18))
    hours = list(range(min(hours[0], 8), max(hours[-1], 17) + 1))
    heatmap = {
        "hours": hours,
        "rows": [{"day": WEEKDAYS[w], "counts": [heat[(w, h)] for h in hours]} for w in range(7)],
        "max": max(heat.values(), default=0),
    }

    by_doctor = defaultdict(lambda: {"seen": 0, "waits": [], "consults": []})
    for v in visits:
        if v.status == Visit.COMPLETED and v.doctor_id:
            row = by_doctor[_name(v.doctor)]
            row["seen"] += 1
            row["waits"].append(_minutes(v.checked_in_at, v.called_at))
            row["consults"].append(_minutes(v.started_at, v.completed_at))
    doctors = sorted(
        ({"name": n, "seen": r["seen"], "avg_wait_min": _avg(r["waits"]), "avg_consult_min": _avg(r["consults"])} for n, r in by_doctor.items()),
        key=lambda r: -r["seen"],
    )

    # New patients: their first visit ever falls in the period.
    patient_ids = {v.patient_id for v in visits}
    earlier = set(
        Visit.objects.filter(patient_id__in=patient_ids, queue_date__lt=start).values_list("patient_id", flat=True).distinct()
    )
    new_patients = len(patient_ids - earlier)

    # Blood pressure: the latest reading per patient per day, by category.
    bp_counts = Counter()
    latest = {}
    for m in (
        Measurement.objects.filter(measured_at__date__gte=start, systolic_bp__isnull=False, diastolic_bp__isnull=False)
        .order_by("measured_at")
        .only("patient_id", "measured_at", "systolic_bp", "diastolic_bp")
    ):
        latest[(m.patient_id, timezone.localtime(m.measured_at).date())] = m
    for m in latest.values():
        bp_counts[bp_category(m.systolic_bp, m.diastolic_bp).key] += 1

    total = len(visits)
    completed = sum(r["completed"] for r in daily)
    lost = sum(r["cancelled"] + r["no_show"] for r in daily)
    return {
        "days": days,
        "start": start.isoformat(),
        "end": today.isoformat(),
        "kpis": {
            "visits": total,
            "completed": completed,
            "per_day": round(total / days, 1),
            "avg_wait_min": _avg(w for ws in waits.values() for w in ws),
            "avg_consult_min": _avg(c for cs in consults.values() for c in cs),
            "lost_rate": round(100 * lost / total) if total else None,
            "patients": len(patient_ids),
            "new_patients": new_patients,
            "online_share": round(100 * sum(1 for v in visits if v.source == Visit.SOURCE_ONLINE) / total) if total else None,
        },
        "daily": daily,
        "heatmap": heatmap,
        "doctors": doctors,
        "bp_categories": [
            {"key": c.key, "label": c.label, "status": c.status, "icon": c.icon, "count": bp_counts[c.key]} for c in BP_CATEGORIES
        ],
    }
