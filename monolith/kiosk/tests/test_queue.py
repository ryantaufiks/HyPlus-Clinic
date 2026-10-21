import datetime as dt
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import queue
from kiosk.models import Measurement, Patient, StaffProfile, Visit
from kiosk.roles import apply_role


def user_with_role(username, role, room=""):
    user = get_user_model().objects.create_user(username, password="a-long-password-123", first_name=username.title())
    apply_role(user, role)
    if room:
        StaffProfile.objects.create(user=user, room=room)
    return user


class QueueFlowTest(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = user_with_role("budi", "doctor", room="Room 1")
        today = timezone.localdate()
        self.visits = [
            Visit.objects.create(patient=Patient.objects.create(name=f"Patient {i}"), reason="r", queue_date=today, queue_number=f"A00{i}")
            for i in (1, 2, 3)
        ]
        # A003 is a hypertensive crisis and is called first.
        Measurement.objects.create(patient=self.visits[2].patient, visit=self.visits[2], systolic_bp=190, diastolic_bp=125)

    def test_call_next_order_room_and_recall(self):
        first = queue.call_next(self.doctor)
        self.assertEqual((first.queue_number, first.status, first.room, first.doctor), ("A003", Visit.CALLED, "Room 1", self.doctor))
        self.assertEqual(queue.call_next(self.doctor).queue_number, "A001")
        again = queue.call(first, self.doctor)
        self.assertEqual(again.call_count, 2)

    def test_admit_rules(self):
        waiting = self.visits[0]
        with self.assertRaisesMessage(queue.QueueError, "has not been called yet"):
            queue.admit(str(waiting.token), None)
        called = queue.call(waiting, self.doctor)
        admitted = queue.admit(str(called.token), None)
        self.assertEqual(admitted.status, Visit.IN_CONSULTATION)
        self.assertIsNotNone(admitted.started_at)
        self.assertEqual(queue.admit(str(called.token), None).status, Visit.IN_CONSULTATION)  # scanned twice

        old = Visit.objects.create(patient=waiting.patient, reason="r", queue_date=timezone.localdate() - dt.timedelta(days=1), queue_number="A009", status=Visit.CALLED)
        with self.assertRaisesMessage(queue.QueueError, "not for today"):
            queue.admit(str(old.token), None)

    def test_access_control_api(self):
        url = reverse("kiosk:api-access-admit")
        visit = queue.call(self.visits[0], self.doctor)
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.post(url, json.dumps({"token": str(visit.token)}), content_type="application/json").status_code, 403)

        self.client.force_login(user_with_role("desk", "frontdesk"))
        bad = self.client.post(url, json.dumps({"token": "not-a-ticket"}), content_type="application/json")
        self.assertEqual((bad.status_code, bad.json()["ok"]), (400, False))
        early = self.client.post(url, json.dumps({"token": str(self.visits[1].token)}), content_type="application/json")
        self.assertIn("not been called", early.json()["message"])
        ok = self.client.post(url, json.dumps({"token": str(visit.token)}), content_type="application/json").json()
        self.assertEqual((ok["ok"], ok["queue_number"], ok["room"]), (True, "A001", "Room 1"))

    def test_complete_and_call_next(self):
        current = queue.admit(str(queue.call(self.visits[2], self.doctor).token), None)
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse("kiosk:visit-detail", args=[current.pk]),
            {
                "diagnosis": "Hypertensive urgency", "diagnosis_code": "", "doctor_notes": "", "complete_next": "1",
                "prescriptions-TOTAL_FORMS": "0", "prescriptions-INITIAL_FORMS": "0",
                "prescriptions-MIN_NUM_FORMS": "0", "prescriptions-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertRedirects(response, reverse("kiosk:doctor-queue"))
        current.refresh_from_db()
        self.assertEqual(current.status, Visit.COMPLETED)
        self.assertIsNotNone(current.completed_at)
        self.assertEqual(Visit.objects.get(queue_number="A001").status, Visit.CALLED)

    def test_doctor_buttons(self):
        self.client.force_login(self.doctor)
        self.client.post(reverse("kiosk:call-next"))
        self.assertEqual(Visit.objects.get(queue_number="A003").status, Visit.CALLED)
        self.client.post(reverse("kiosk:visit-cancel", args=[self.visits[2].pk]), {"reason": "No-show"})
        self.assertEqual(Visit.objects.get(queue_number="A003").status, Visit.CANCELLED)
        page = self.client.get(reverse("kiosk:doctor-queue"))
        self.assertEqual(page.context["room"], "Room 1")

        self.client.force_login(user_with_role("nurse", "nurse"))
        self.client.post(reverse("kiosk:call-next"))
        self.assertEqual(Visit.objects.filter(status=Visit.CALLED).count(), 0)  # only doctors call patients

    def test_display_shows_numbers_not_names(self):
        queue.admit(str(queue.call(self.visits[2], self.doctor).token), None)
        queue.call(self.visits[0], self.doctor)
        response = self.client.get(reverse("kiosk:display-data"))  # public
        data = response.json()
        self.assertEqual([c["queue_number"] for c in data["called"]], ["A001"])
        self.assertEqual([c["room"] for c in data["in_progress"]], ["Room 1"])
        self.assertEqual(data["waiting"], ["A002"])
        self.assertNotIn("Patient", response.content.decode())
        self.assertEqual(self.client.get(reverse("kiosk:display")).status_code, 200)

    def test_patient_phone_status_and_qr(self):
        visit = self.visits[1]
        status = self.client.get(reverse("kiosk:visit-status", args=[visit.token])).json()
        self.assertEqual((status["status"], status["ahead"]), ("waiting", 2))  # A003 (critical) and A001 go first
        queue.call(visit, self.doctor)
        status = self.client.get(reverse("kiosk:visit-status", args=[visit.token])).json()
        self.assertEqual((status["status"], status["room"]), ("called", "Room 1"))
        png = self.client.get(reverse("kiosk:visit-qr", args=[visit.token]) + "?download=1")
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertIn("attachment", png["Content-Disposition"])
        page = self.client.get(reverse("kiosk:visit-token", args=[visit.token])).content.decode()
        self.assertIn("A002", page)
        self.assertIn("Save QR code", page)


class CancelVisitTest(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.patient = Patient.objects.create(name="Ryan")
        self.visit = Visit.objects.create(patient=self.patient, reason="Dizzy", queue_date=today, queue_number="A001")
        Measurement.objects.create(patient=self.patient, visit=self.visit, systolic_bp=120, diastolic_bp=80)
        self.url = reverse("kiosk:visit-cancel", args=[self.visit.pk])

    def test_reason_is_required(self):
        self.client.force_login(user_with_role("rina", "nurse"))
        self.client.post(self.url, {"reason": "  "})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, Visit.WAITING)

    def test_cancel_keeps_record_and_leaves_the_queue(self):
        nurse = user_with_role("rina", "nurse")
        self.client.force_login(nurse)
        response = self.client.post(self.url, {"reason": "Patient left before being called", "next": "visit"})
        self.assertRedirects(response, reverse("kiosk:visit-detail", args=[self.visit.pk]))
        self.visit.refresh_from_db()
        self.assertEqual((self.visit.status, self.visit.cancel_reason, self.visit.cancelled_by), (Visit.CANCELLED, "Patient left before being called", nurse))
        self.assertEqual(self.visit.measurements.count(), 1)  # vitals kept
        self.assertEqual(self.client.get(reverse("kiosk:display-data")).json()["waiting"], [])
        page = self.client.get(reverse("kiosk:visit-detail", args=[self.visit.pk])).content.decode()
        self.assertIn("Patient left before being called", page)
        self.assertEqual(self.patient.audit_events.get(action="queue.cancelled").detail["reason"], "Patient left before being called")

    def test_who_can_cancel(self):
        for role, allowed in (("frontdesk", False), ("doctor", True), ("admin", True)):
            visit = Visit.objects.create(patient=self.patient, reason="r", queue_date=timezone.localdate(), queue_number=f"B-{role}"[:10])
            self.client.force_login(user_with_role(f"u{role}", role))
            response = self.client.post(reverse("kiosk:visit-cancel", args=[visit.pk]), {"reason": "Duplicate ticket"})
            visit.refresh_from_db()
            self.assertEqual(visit.status == Visit.CANCELLED, allowed, role)
            if not allowed:
                self.assertEqual(response.status_code, 403)

    def test_completed_visit_cannot_be_cancelled(self):
        Visit.objects.filter(pk=self.visit.pk).update(status=Visit.COMPLETED)
        self.client.force_login(user_with_role("rina", "nurse"))
        self.client.post(self.url, {"reason": "Mistake"})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, Visit.COMPLETED)

    def test_cancel_button_shown_by_role(self):
        self.client.force_login(user_with_role("dr", "doctor", room="Room 1"))
        self.assertContains(self.client.get(reverse("kiosk:doctor-queue")), "Cancel visit")
        self.client.force_login(user_with_role("desk", "frontdesk"))
        self.assertNotContains(self.client.get(reverse("kiosk:visit-detail", args=[self.visit.pk])), "Cancel visit")


class DisplayRoomsTest(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.budi = user_with_role("budi", "doctor", room="Room 10")
        self.siti = user_with_role("siti", "doctor", room="Room 2")
        self.away = user_with_role("away", "doctor", room="Room 3")
        StaffProfile.objects.filter(user=self.away).update(on_duty=False)
        user_with_role("noroom", "doctor")
        user_with_role("nurse", "nurse", room="Triage")
        self.visit = Visit.objects.create(patient=Patient.objects.create(name="Ryan"), reason="r", queue_date=today, queue_number="A001")

    def rooms(self):
        return self.client.get(reverse("kiosk:display-data")).json()["rooms"]

    def test_all_on_duty_rooms_in_natural_order(self):
        self.assertEqual(
            [(r["room"], r["doctor"], r["state"]) for r in self.rooms()],
            [("Room 2", "Siti", "available"), ("Room 10", "Budi", "available")],
        )

    def test_room_states_follow_the_patient(self):
        queue.call(self.visit, self.budi)
        self.assertEqual([(r["room"], r["state"], r["queue_number"]) for r in self.rooms()][1], ("Room 10", "called", "A001"))
        queue.admit(str(self.visit.token), None)
        self.assertEqual(self.rooms()[1]["state"], "in_progress")

    def test_duty_toggle_and_calling_puts_doctor_on_duty(self):
        self.client.force_login(self.siti)
        self.client.post(reverse("kiosk:doctor-duty"), {"on_duty": "0"})
        self.assertEqual([r["room"] for r in self.rooms()], ["Room 10"])
        self.assertContains(self.client.get(reverse("kiosk:doctor-queue")), "Off duty")
        queue.call(self.visit, self.siti)
        self.assertEqual([r["room"] for r in self.rooms()], ["Room 2", "Room 10"])

    def test_off_duty_doctor_with_patient_still_shown(self):
        queue.call(self.visit, self.budi)
        StaffProfile.objects.filter(user=self.budi).update(on_duty=False)
        self.assertIn(("Room 10", "called"), [(r["room"], r["state"]) for r in self.rooms()])


class StaffRoomTest(TestCase):
    def test_doctor_needs_room(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="a-long-password-123"))
        data = {"first_name": "Budi", "last_name": "", "username": "dr.budi", "email": "", "role": "doctor", "room": ""}
        self.assertEqual(self.client.post(reverse("kiosk:staff-create"), data).status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="dr.budi").exists())
        self.client.post(reverse("kiosk:staff-create"), {**data, "room": "Room 2"})
        self.assertEqual(StaffProfile.room_for(get_user_model().objects.get(username="dr.budi")), "Room 2")
