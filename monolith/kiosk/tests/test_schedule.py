import datetime as dt

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import schedule
from kiosk.models import BookingRequest, DoctorSchedule, DoctorTimeOff

from .test_queue import user_with_role
from .test_website import booking_data


def week(**days):
    """POST data for the weekly form: week(mon=[("08:00", "12:00")], ...)."""
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    data = {"action": "hours"}
    for weekday, name in enumerate(names):
        for i, (start, end) in enumerate(days.get(name, [])):
            data[f"day-{weekday}-on"] = "1"
            data[f"day-{weekday}-start{i}"] = start
            data[f"day-{weekday}-end{i}"] = end
    return data


def next_weekday(weekday):
    today = timezone.localdate()
    return today + dt.timedelta(days=(weekday - today.weekday()) % 7 or 7)


class ScheduleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = user_with_role("budi", "doctor", room="Room 1")
        self.url = reverse("kiosk:my-schedule")

    def test_doctor_sets_weekly_hours(self):
        self.client.force_login(self.doctor)
        weekday = [("08:00", "12:00"), ("17:00", "20:00")]
        self.client.post(self.url, week(mon=weekday, tue=weekday, wed=weekday, sat=[("09:00", "12:00")]))
        self.assertEqual(DoctorSchedule.objects.filter(doctor=self.doctor).count(), 7)
        self.assertEqual(schedule.summary(self.doctor), "Mon–Wed 08:00–12:00, 17:00–20:00 · Sat 09:00–12:00")
        page = self.client.get(reverse("kiosk:schedules"))
        self.assertContains(page, "<div>08:00–12:00</div><div>17:00–20:00</div>", html=False)

    def test_invalid_hours_are_rejected_and_nothing_is_saved(self):
        self.client.force_login(self.doctor)
        self.assertContains(self.client.post(self.url, week(mon=[("12:00", "08:00")])), "start time before its end time")
        self.assertContains(self.client.post(self.url, week(mon=[("08:00", "12:00"), ("11:00", "14:00")])), "overlap")
        self.assertContains(self.client.post(self.url, {"action": "hours", "day-0-on": "1"}), "Add your hours")
        self.assertFalse(DoctorSchedule.objects.exists())

    def test_days_off(self):
        self.client.force_login(self.doctor)
        date = timezone.localdate() + dt.timedelta(days=3)
        self.client.post(self.url, {"action": "add_off", "date": date.isoformat(), "note": "Annual leave"})
        off = DoctorTimeOff.objects.get(doctor=self.doctor)
        self.assertEqual((off.date, off.note), (date, "Annual leave"))
        self.client.post(self.url, {"action": "add_off", "date": "2000-01-01"})
        self.assertEqual(DoctorTimeOff.objects.count(), 1)
        self.client.post(self.url, {"action": "remove_off", "time_off": off.pk})
        self.assertFalse(DoctorTimeOff.objects.exists())

    def test_who_can_edit(self):
        other = user_with_role("sari", "doctor", room="Room 2")
        nurse = user_with_role("nurse", "nurse")
        admin = get_user_model().objects.create_superuser("admin", password="a-long-password-123")
        other_url = reverse("kiosk:staff-schedule", args=[other.pk])
        self.client.force_login(nurse)
        self.assertEqual(self.client.get(self.url).status_code, 403)  # not a doctor
        self.assertEqual(self.client.get(reverse("kiosk:schedules")).status_code, 200)  # but sees everyone's week
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.post(other_url, week(mon=[("08:00", "12:00")])).status_code, 403)
        self.client.force_login(admin)
        self.client.post(other_url, week(fri=[("13:00", "17:00")]))
        self.assertEqual(schedule.summary(other), "Fri 13:00–17:00")


class BookingAgainstScheduleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = user_with_role("budi", "doctor", room="Room 1")
        DoctorSchedule.objects.create(doctor=self.doctor, weekday=0, start_time=dt.time(8), end_time=dt.time(12))  # Mondays, mornings

    def book(self, date, time="morning", doctor=None):
        return self.client.post(reverse("kiosk:book"), booking_data(
            preferred_doctor=(doctor or self.doctor).pk, preferred_date=date.isoformat(), preferred_time=time,
        ))

    def test_bookings_follow_the_schedule(self):
        monday, tuesday = next_weekday(0), next_weekday(1)
        self.assertContains(self.book(tuesday), "does not work on Tuesdays")
        self.assertContains(self.book(monday, "evening"), "is not in at that time")
        DoctorTimeOff.objects.create(doctor=self.doctor, date=monday, note="Conference")
        self.assertContains(self.book(monday), "not available on")
        DoctorTimeOff.objects.all().delete()
        self.assertContains(self.book(monday), "Booking request sent")
        self.assertEqual(BookingRequest.objects.count(), 1)

    def test_doctor_without_a_schedule_is_not_restricted(self):
        free = user_with_role("sari", "doctor", room="Room 2")
        self.assertContains(self.book(next_weekday(6), "evening", doctor=free), "Booking request sent")

    def test_booking_page_shows_hours(self):
        self.assertContains(self.client.get(reverse("kiosk:book")), "Mon 08:00\\u201312:00")  # JSON-escaped en dash
