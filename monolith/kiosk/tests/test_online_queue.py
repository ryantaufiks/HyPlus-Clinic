import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import queue
from kiosk.models import Patient, StaffProfile, Visit

from .test_queue import user_with_role


def ticket_data(**overrides):
    data = {"doctor": "", "name": "Dewi Lestari", "phone": "0812 3456 7890", "patient_id": "", "reason": "Cough", "consent": "on", "website": ""}
    data.update(overrides)
    return data


class OnlineQueueTest(TestCase):
    def setUp(self):
        cache.clear()
        self.doctor = user_with_role("budi", "doctor", room="Room 1")

    def take(self, **overrides):
        return self.client.post(reverse("kiosk:queue-ticket"), ticket_data(**overrides))

    def kiosk_visit(self, number):
        return Visit.objects.create(patient=Patient.objects.create(name=f"Walk-in {number}"), reason="r", queue_date=timezone.localdate(), queue_number=number)

    def test_online_ticket_keeps_its_place_but_is_called_after_check_in(self):
        self.kiosk_visit("A001")
        response = self.take(doctor=self.doctor.pk)
        online = Visit.objects.get(source=Visit.SOURCE_ONLINE)
        self.assertRedirects(response, reverse("kiosk:visit-token", args=[online.token]) + "?new=1", fetch_redirect_response=False)
        self.assertEqual((online.queue_number, online.requested_doctor, online.checked_in_at), ("A002", self.doctor, None))
        self.kiosk_visit("A003")

        status = self.client.get(reverse("kiosk:visit-status", args=[online.token])).json()
        self.assertEqual((status["checked_in"], status["ahead"]), (False, 1))
        self.assertContains(self.client.get(reverse("kiosk:visit-token", args=[online.token]) + "?new=1"), "Check in when you arrive")

        # Not checked in: skipped by Call next, refused by a manual call, not on the TV.
        self.assertEqual(queue.call_next(self.doctor).queue_number, "A001")
        with self.assertRaisesMessage(queue.QueueError, "has not checked in"):
            queue.call(online, self.doctor)
        waiting_on_tv = [w["queue_number"] for w in self.client.get(reverse("kiosk:display-data")).json()["waiting"]]
        self.assertEqual(waiting_on_tv, ["A003"])

        # Checked in: called before A003, which came later.
        self.assertTrue(queue.check_in(online))
        self.assertEqual(queue.call_next(self.doctor).queue_number, "A002")

    def test_kiosk_check_in_needs_number_and_phone_digits(self):
        self.take()
        online = Visit.objects.get(source=Visit.SOURCE_ONLINE)
        url = reverse("kiosk:api-online-checkin")
        wrong = self.client.post(url, json.dumps({"queue_number": "a001", "phone_last4": "0000"}), content_type="application/json")
        self.assertEqual(wrong.status_code, 404)
        ok = self.client.post(url, json.dumps({"queue_number": "a001", "phone_last4": "7890"}), content_type="application/json")
        self.assertEqual((ok.status_code, ok.json()["token"]), (200, str(online.token)))
        online.refresh_from_db()
        self.assertTrue(online.is_checked_in)

    def test_door_scanner_checks_in_an_online_ticket(self):
        self.take()
        online = Visit.objects.get(source=Visit.SOURCE_ONLINE)
        self.client.force_login(user_with_role("desk", "frontdesk"))
        data = self.client.post(reverse("kiosk:api-access-admit"), json.dumps({"token": str(online.token)}), content_type="application/json").json()
        self.assertEqual((data["ok"], data["checked_in"]), (True, True))
        online.refresh_from_db()
        self.assertEqual((online.status, online.is_checked_in), (Visit.WAITING, True))

    def test_one_ticket_per_phone_and_patient_id_must_match_phone(self):
        self.take()
        self.assertContains(self.take(phone="+62 812-3456-7890"), "already has a queue ticket for today")
        existing = Patient.objects.create(name="Ryan", phone="0811 1111 2222")
        self.assertContains(self.take(phone="0899 9999 9999", patient_id=existing.patient_id), "does not match this WhatsApp number")
        self.take(phone="0811 1111 2222", patient_id=existing.patient_id.lower())
        self.assertEqual(Visit.objects.filter(patient=existing).count(), 1)

    def test_closed_without_doctors_on_duty(self):
        StaffProfile.objects.filter(user=self.doctor).update(on_duty=False)
        self.assertContains(self.client.get(reverse("kiosk:queue-ticket")), "online queue is closed")
        self.take()
        self.assertFalse(Visit.objects.exists())

    def test_staff_see_and_check_in_patients_who_have_not_arrived(self):
        self.take()
        online = Visit.objects.get(source=Visit.SOURCE_ONLINE)
        self.client.force_login(user_with_role("nurse", "nurse"))
        self.assertContains(self.client.get(reverse("kiosk:doctor-queue")), "not arrived yet")
        self.client.post(reverse("kiosk:visit-check-in", args=[online.pk]), {"next": "queue"})
        online.refresh_from_db()
        self.assertTrue(online.is_checked_in)
