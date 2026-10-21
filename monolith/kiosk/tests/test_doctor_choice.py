import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from kiosk import queue
from kiosk.models import Patient, StaffProfile, Visit

from .test_queue import user_with_role


class DoctorChoiceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.budi = user_with_role("budi", "doctor", room="Room 1")
        self.sari = user_with_role("sari", "doctor", room="Room 2")
        self.today = timezone.localdate()

    def visit(self, number, doctor=None):
        return Visit.objects.create(
            patient=Patient.objects.create(name=f"Patient {number}"), reason="r",
            queue_date=self.today, queue_number=number, requested_doctor=doctor,
        )

    def start(self, **body):
        return self.client.post(reverse("kiosk:api-visit-start"), json.dumps({"name": "Dewi", "reason": "Cough", **body}), content_type="application/json")

    def test_kiosk_lists_doctors_on_duty_with_their_lines(self):
        user_with_role("nurse", "nurse", room="Triage")  # not a doctor
        self.visit("A001", self.sari)
        self.visit("A002")
        data = self.client.get(reverse("kiosk:api-doctors")).json()  # public, for the kiosk
        self.assertEqual([(d["name"], d["room"], d["waiting"]) for d in data["doctors"]], [("Budi", "Room 1", 0), ("Sari", "Room 2", 1)])
        self.assertEqual(data["any_waiting"], 1)

    def test_visit_start_stores_the_chosen_doctor(self):
        response = self.start(doctor_id=self.sari.pk)
        self.assertEqual((response.status_code, response.json()["room"]), (201, "Room 2"))
        self.assertEqual(Visit.objects.get().requested_doctor, self.sari)
        self.assertEqual(self.start(doctor_id="").status_code, 201)
        self.assertIsNone(Visit.objects.latest("pk").requested_doctor)  # first available doctor

        StaffProfile.objects.filter(user=self.sari).update(on_duty=False)
        self.assertEqual(self.start(doctor_id=self.sari.pk).status_code, 409)
        nurse = user_with_role("nurse", "nurse", room="Triage")
        self.assertEqual(self.start(doctor_id=nurse.pk).status_code, 409)

    def test_each_doctor_calls_their_own_line_and_any_doctor_patients(self):
        self.visit("A001", self.sari)
        self.visit("A002", self.budi)
        self.visit("A003")
        self.assertEqual(queue.call_next(self.budi).queue_number, "A002")
        self.assertEqual(queue.call_next(self.budi).queue_number, "A003")
        self.assertIsNone(queue.call_next(self.budi))  # A001 waits for Sari
        self.assertEqual(queue.call_next(self.sari).queue_number, "A001")

    def test_patients_of_a_doctor_who_went_off_duty_join_every_line(self):
        sari_patient = self.visit("A001", self.sari)
        self.visit("A002", self.budi)
        self.assertEqual(queue.position(sari_patient), 0)
        StaffProfile.objects.filter(user=self.sari).update(on_duty=False)
        self.assertEqual(queue.call_next(self.budi).queue_number, "A001")

    def test_position_counts_only_the_chosen_doctor_line(self):
        self.visit("A001", self.sari)
        self.visit("A002", self.sari)
        mine = self.visit("A003", self.budi)
        self.assertEqual(queue.position(mine), 0)
        anyone = self.visit("A004")
        self.assertEqual(queue.position(anyone), 3)  # conservative: everyone ahead

    def test_tv_shows_each_doctor_line(self):
        self.visit("A001", self.sari)
        self.visit("A002")
        data = self.client.get(reverse("kiosk:display-data")).json()
        self.assertEqual(data["waiting"], [{"queue_number": "A001", "room": "Room 2"}, {"queue_number": "A002", "room": ""}])
        rooms = {r["room"]: (r["waiting"], r["next"]) for r in data["rooms"]}
        self.assertEqual(rooms, {"Room 1": (0, []), "Room 2": (1, ["A001"])})

    def test_doctors_see_and_call_only_their_own_line(self):
        sari_patient = self.visit("A001", self.sari)
        self.visit("A002")
        done = self.visit("A003", self.sari)
        queue.call(done, self.sari)
        self.client.force_login(self.budi)
        response = self.client.get(reverse("kiosk:doctor-queue"))
        self.assertEqual([r["visit"].queue_number for r in response.context["my_line"]], ["A002"])
        self.assertEqual(response.context["others"], [])  # Sari's called patient is not shown
        self.assertNotContains(response, "Patient A001")
        self.assertNotContains(response, "Patient A003")

        self.client.post(reverse("kiosk:visit-call", args=[sari_patient.pk]), {"next": "queue"})
        self.assertEqual(Visit.objects.get(pk=sari_patient.pk).status, Visit.WAITING)
        self.client.post(reverse("kiosk:visit-call", args=[done.pk]), {"next": "queue"})  # no recall of Sari's call
        self.assertEqual(Visit.objects.get(pk=done.pk).doctor, self.sari)

        nurse = user_with_role("nurse", "nurse")
        self.client.force_login(nurse)  # nurses still see the whole queue
        self.assertEqual(len(self.client.get(reverse("kiosk:doctor-queue")).context["waiting"]), 2)
