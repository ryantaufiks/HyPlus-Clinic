import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import analytics
from kiosk.models import Patient, StaffProfile, Visit
from kiosk.roles import apply_role


def user_with_role(username, role):
    user = get_user_model().objects.create_user(username, password="a-long-password-123", first_name=username.title())
    apply_role(user, role)
    return user


class TodayOverviewTest(TestCase):
    def setUp(self):
        self.doctor = user_with_role("budi", "doctor")
        StaffProfile.objects.create(user=self.doctor, room="Room 1")
        self.today = timezone.localdate()
        self.now = timezone.now()

    def visit(self, number, status=Visit.WAITING, **fields):
        return Visit.objects.create(patient=Patient.objects.create(name=f"P {number}"), reason="r",
                                    queue_date=self.today, queue_number=number, status=status, **fields)

    def test_called_patients_stay_on_the_dashboard_and_counts_are_not_capped(self):
        for i in range(30):
            self.visit(f"A{i:03}", checked_in_at=self.now - dt.timedelta(minutes=40 - i))
        self.visit("B001", Visit.CALLED, doctor=self.doctor, room="Room 1",
                   checked_in_at=self.now - dt.timedelta(minutes=20), called_at=self.now - dt.timedelta(minutes=5))
        self.visit("B002", Visit.IN_CONSULTATION, doctor=self.doctor, checked_in_at=self.now, called_at=self.now, started_at=self.now)
        self.visit("C001", source=Visit.SOURCE_ONLINE, checked_in_at=None)

        data = analytics.today_overview()
        k = data["kpis"]
        self.assertEqual(k["waiting"], 30)  # in consultation is not "waiting"; no cap at 25
        self.assertEqual((k["not_arrived"], k["with_doctor"]), (1, 2))
        self.assertEqual((k["longest_wait_ticket"], k["longest_wait_min"]), ("A000", 40))
        self.assertEqual(k["avg_wait_min"], 7.5)  # (15 + 0) / 2
        statuses = [r["status"] for r in data["queue"]]
        self.assertEqual(statuses[:2], ["Called", "In consultation"])
        self.assertEqual(statuses[-1], "Not arrived")
        self.assertEqual(data["queue_total"], 33)
        self.assertEqual(data["doctors"][0]["serving"], "B002")


class PeriodReportTest(TestCase):
    def test_outcomes_times_and_new_patients(self):
        doctor = user_with_role("budi", "doctor")
        today = timezone.localdate()
        old = Patient.objects.create(name="Returning")
        Visit.objects.create(patient=old, reason="r", queue_date=today - dt.timedelta(days=60), queue_number="A001", status=Visit.COMPLETED)
        t = timezone.now() - dt.timedelta(hours=2)
        Visit.objects.create(patient=old, reason="r", queue_date=today, queue_number="A001", status=Visit.COMPLETED, doctor=doctor,
                             checked_in_at=t, called_at=t + dt.timedelta(minutes=10), started_at=t + dt.timedelta(minutes=12),
                             completed_at=t + dt.timedelta(minutes=27))
        Visit.objects.create(patient=Patient.objects.create(name="New"), reason="r", queue_date=today, queue_number="A002",
                             status=Visit.CANCELLED, cancel_reason="No-show")
        Visit.objects.create(patient=Patient.objects.create(name="Gone"), reason="r", queue_date=today - dt.timedelta(days=1),
                             queue_number="A001", status=Visit.WAITING)  # never seen: counts as a no-show

        report = analytics.period_report(7)
        k = report["kpis"]
        self.assertEqual((k["visits"], k["completed"], k["patients"], k["new_patients"]), (3, 1, 3, 2))
        self.assertEqual((k["avg_wait_min"], k["avg_consult_min"], k["lost_rate"]), (10.0, 15.0, 67))
        self.assertEqual(sum(d["no_show"] for d in report["daily"]), 2)
        self.assertEqual(report["doctors"][0], {"name": "Budi", "seen": 1, "avg_wait_min": 10.0, "avg_consult_min": 15.0})
        self.assertEqual(len(report["daily"]), 7)


class AnalyticsPageTest(TestCase):
    def test_only_administrators_open_analytics(self):
        url = reverse("kiosk:analytics")
        self.client.force_login(user_with_role("ada", "admin"))
        page = self.client.get(url, {"days": 90})
        self.assertContains(page, "Last 90 days")
        self.assertContains(page, "Busiest hours")
        self.assertEqual(self.client.get(url, {"days": "abc"}).context["days"], 30)
        self.assertContains(self.client.get(reverse("kiosk:dashboard")), url)
        for name, role in [("nina", "nurse"), ("fd", "frontdesk"), ("doc", "doctor")]:
            self.client.force_login(user_with_role(name, role))
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertNotContains(self.client.get(reverse("kiosk:dashboard")), url)
