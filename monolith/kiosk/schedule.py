"""Doctors' weekly consulting hours and days off.

A doctor who has not set any hours yet has no schedule: bookings for them
are not restricted, so nothing breaks before schedules are filled in.
"""

import datetime as dt

from .models import BookingRequest, DoctorSchedule, DoctorTimeOff

WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BLOCKS_PER_DAY = 2

# The booking form's times of day, as clock hours.
PERIODS = {
    BookingRequest.MORNING: (dt.time(8), dt.time(12)),
    BookingRequest.AFTERNOON: (dt.time(12), dt.time(17)),
    BookingRequest.EVENING: (dt.time(17), dt.time(20)),
}


def weekly(doctor):
    """{weekday: [(start, end), ...]} for one doctor."""
    days = {}
    for block in DoctorSchedule.objects.filter(doctor=doctor):
        days.setdefault(block.weekday, []).append((block.start_time, block.end_time))
    return days


def has_schedule(doctor):
    return DoctorSchedule.objects.filter(doctor=doctor).exists()


def hours_on(doctor, date):
    """Consulting hours on a date: [] on a day off or a day the doctor does not work."""
    if DoctorTimeOff.objects.filter(doctor=doctor, date=date).exists():
        return []
    return [(b.start_time, b.end_time) for b in DoctorSchedule.objects.filter(doctor=doctor, weekday=date.weekday())]


def availability_error(doctor, date, period=None):
    """Why the doctor cannot be booked then, or "" when they can (or have no schedule)."""
    if doctor is None or date is None or not has_schedule(doctor):
        return ""
    name = doctor.get_full_name() or doctor.get_username()
    off = DoctorTimeOff.objects.filter(doctor=doctor, date=date).first()
    if off:
        return f"{name} is not available on {date:%A %d %B}{f' ({off.note})' if off.note else ''}."
    hours = hours_on(doctor, date)
    if not hours:
        return f"{name} does not work on {date:%A}s. Their hours: {summary(doctor)}."
    if period in PERIODS:
        start, end = PERIODS[period]
        if not any(b_start < end and start < b_end for b_start, b_end in hours):
            return f"{name} is not in at that time on {date:%A}: {format_blocks(hours)}."
    return ""


def format_blocks(blocks):
    return ", ".join(f"{start:%H:%M}–{end:%H:%M}" for start, end in blocks)


def summary(doctor):
    """"Mon–Fri 08:00–12:00 · Sat 09:00–12:00" style summary, or "" without a schedule."""
    days = weekly(doctor)
    groups = []  # consecutive weekdays with the same hours
    for weekday in range(7):
        if weekday not in days:
            continue
        text = format_blocks(days[weekday])
        if groups and groups[-1][1] == weekday - 1 and groups[-1][2] == text:
            groups[-1][1] = weekday
        else:
            groups.append([weekday, weekday, text])
    return " · ".join(
        f"{WEEKDAY_SHORT[a]}{'–' + WEEKDAY_SHORT[b] if b != a else ''} {text}" for a, b, text in groups
    )


def week_grid(doctors):
    """Rows for a week table: each doctor with their hours per weekday."""
    blocks = {}
    for block in DoctorSchedule.objects.filter(doctor__in=doctors):
        blocks.setdefault((block.doctor_id, block.weekday), []).append((block.start_time, block.end_time))
    return [
        {
            "doctor": d,
            "days": [[format_blocks([b]) for b in blocks.get((d.pk, w), [])] for w in range(7)],
            "has_schedule": any((d.pk, w) in blocks for w in range(7)),
        }
        for d in doctors
    ]
