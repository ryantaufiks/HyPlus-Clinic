"""Doctors set their weekly consulting hours and days off; staff see everyone's week."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from . import schedule
from .models import AuditEvent, DoctorSchedule, DoctorTimeOff
from .roles import DOCTOR_GROUP, StaffAreaMixin, is_doctor

User = get_user_model()


def doctors():
    return User.objects.filter(is_active=True, groups__name=DOCTOR_GROUP).order_by("first_name", "last_name", "username")


def _time(value):
    try:
        return dt.time.fromisoformat(value) if value else None
    except ValueError:
        return None


class ScheduleEditView(StaffAreaMixin, View):
    """/me/schedule/ for a doctor's own hours; /staff/<pk>/schedule/ for administrators."""

    template_name = "kiosk/schedule_edit.html"

    def _doctor(self, request, pk):
        if pk is None:
            if not is_doctor(request.user):
                raise PermissionDenied
            return request.user
        if not request.user.is_superuser and request.user.pk != pk:
            raise PermissionDenied
        return get_object_or_404(doctors(), pk=pk)

    def _render(self, request, doctor, days=None, errors=None):
        current = schedule.weekly(doctor)
        if days is None:
            days = [
                {
                    "weekday": w,
                    "name": name,
                    "on": w in current,
                    "blocks": [
                        {"start": f"{s:%H:%M}", "end": f"{e:%H:%M}"} for s, e in current.get(w, [])
                    ] + [{"start": "", "end": ""}] * (schedule.BLOCKS_PER_DAY - len(current.get(w, []))),
                }
                for w, name in DoctorSchedule.WEEKDAYS
            ]
        return render(
            request,
            self.template_name,
            {
                "doctor": doctor,
                "own": doctor == request.user,
                "days": days,
                "errors": errors or {},
                "summary": schedule.summary(doctor),
                "time_off": DoctorTimeOff.objects.filter(doctor=doctor, date__gte=timezone.localdate()),
                "today": timezone.localdate().isoformat(),
            },
        )

    def get(self, request, pk=None):
        return self._render(request, self._doctor(request, pk))

    def post(self, request, pk=None):
        doctor = self._doctor(request, pk)
        action = request.POST.get("action", "hours")
        if action == "add_off":
            return self._add_time_off(request, doctor)
        if action == "remove_off":
            DoctorTimeOff.objects.filter(doctor=doctor, pk=request.POST.get("time_off")).delete()
            messages.info(request, "Day off removed.")
            return redirect(request.path)

        days, errors, blocks = [], {}, []
        for weekday, name in DoctorSchedule.WEEKDAYS:
            on = request.POST.get(f"day-{weekday}-on") == "1"
            entered = [
                {"start": request.POST.get(f"day-{weekday}-start{i}", ""), "end": request.POST.get(f"day-{weekday}-end{i}", "")}
                for i in range(schedule.BLOCKS_PER_DAY)
            ]
            days.append({"weekday": weekday, "name": name, "on": on, "blocks": entered})
            if not on:
                continue
            day_blocks = []
            for block in entered:
                start, end = _time(block["start"]), _time(block["end"])
                if not block["start"] and not block["end"]:
                    continue
                if start is None or end is None or start >= end:
                    errors[weekday] = "Each session needs a start time before its end time."
                    break
                day_blocks.append((start, end))
            else:
                day_blocks.sort()
                if not day_blocks:
                    errors[weekday] = "Add your hours, or switch the day off."
                elif any(a[1] > b[0] for a, b in zip(day_blocks, day_blocks[1:])):
                    errors[weekday] = "The two sessions overlap."
            blocks += [(weekday, s, e) for s, e in day_blocks]
        if errors:
            messages.error(request, "Please check the highlighted days.")
            return self._render(request, doctor, days, errors)

        with transaction.atomic():
            DoctorSchedule.objects.filter(doctor=doctor).delete()
            DoctorSchedule.objects.bulk_create(DoctorSchedule(doctor=doctor, weekday=w, start_time=s, end_time=e) for w, s, e in blocks)
            AuditEvent.record(request.user, "schedule.updated", doctor=doctor.pk, summary=schedule.summary(doctor))
        messages.success(request, "Weekly schedule saved." if blocks else "Weekly schedule cleared.")
        return redirect(request.path)

    def _add_time_off(self, request, doctor):
        try:
            date = dt.date.fromisoformat(request.POST.get("date", ""))
        except ValueError:
            messages.error(request, "Choose a date for the day off.")
            return redirect(request.path)
        if date < timezone.localdate():
            messages.error(request, "Choose today or a later date.")
            return redirect(request.path)
        _, created = DoctorTimeOff.objects.update_or_create(
            doctor=doctor, date=date, defaults={"note": " ".join(request.POST.get("note", "").split())[:80]}
        )
        AuditEvent.record(request.user, "schedule.time_off", doctor=doctor.pk, date=date.isoformat())
        messages.success(request, f"{date:%A %d %B} marked as a day off.")
        return redirect(request.path)


class ScheduleOverviewView(StaffAreaMixin, TemplateView):
    """Every doctor's week at a glance, with upcoming days off."""

    template_name = "kiosk/schedules.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        doctor_list = list(doctors())
        context.update(
            {
                "rows": schedule.week_grid(doctor_list),
                "weekdays": schedule.WEEKDAY_SHORT,
                "today_weekday": today.weekday(),
                "time_off": DoctorTimeOff.objects.filter(doctor__in=doctor_list, date__gte=today, date__lte=today + dt.timedelta(days=30)).select_related("doctor"),
                "is_doctor": is_doctor(self.request.user),
            }
        )
        return context
