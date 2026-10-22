"""Fictional data for UI screenshots (local demo container only)."""
import datetime as dt
import random
from django.contrib.auth import get_user_model
from django.utils import timezone
from kiosk import queue
from kiosk.models import (DoctorSchedule, Measurement, Patient, PrescriptionItem, Review, StaffProfile, Visit)
from kiosk.portal_views import ensure_portal_user
from kiosk.roles import apply_role

random.seed(7)
U = get_user_model()
PW = "demo-pass-12345"
U.objects.create_superuser("admin", password=PW, first_name="Clinic", last_name="Admin")
docs = []
for u, f, l, room in [("budi", "Dr. Budi", "Santoso", "Room 1"), ("sari", "Dr. Sari", "Wijaya", "Room 2"), ("andi", "Dr. Andi", "Pratama", "Room 3")]:
    d = U.objects.create_user(u, password=PW, first_name=f, last_name=l); apply_role(d, "doctor")
    StaffProfile.objects.create(user=d, room=room); docs.append(d)
    for w in range(5):
        DoctorSchedule.objects.create(doctor=d, weekday=w, start_time=dt.time(8), end_time=dt.time(12))
        DoctorSchedule.objects.create(doctor=d, weekday=w, start_time=dt.time(17), end_time=dt.time(20))
nurse = U.objects.create_user("nurse", password=PW, first_name="Rina", last_name="Lestari"); apply_role(nurse, "nurse")

names = ["Maya Putri", "Hendra Gunawan", "Siti Rahma", "Agus Salim", "Dewi Anggraini", "Rizal Hakim", "Lina Marlina",
         "Tono Saputra", "Nadia Ayu", "Bayu Firmansyah", "Fitri Handayani", "Yoga Pratama", "Citra Kirana", "Joko Susilo"]
now = timezone.now(); today = timezone.localdate()
reasons = ["Fever and sore throat", "Headache for three days", "Routine blood pressure check", "Cough and runny nose",
           "Back pain after lifting", "Follow-up on medication", "Dizziness in the morning", "Skin rash on the arm"]
patients = []
for i, name in enumerate(names):
    p = Patient.objects.create(name=name, phone=f"0812 5555 {1000 + i}", date_of_birth=dt.date(1960 + i * 3, (i % 12) + 1, 10),
                               height_cm=150 + i * 2, has_drug_allergy=(i % 4 == 0), drug_allergies="Penicillin" if i % 4 == 0 else "",
                               medical_history="Hypertension, on amlodipine" if i % 3 == 0 else "")
    patients.append(p)
    # Past visits over six weeks for trends.
    for k in range(4):
        when = now - dt.timedelta(days=7 * (k + 1) + i % 5)
        v = Visit.objects.create(patient=p, reason=random.choice(reasons), status=Visit.COMPLETED, doctor=random.choice(docs),
                                 diagnosis=random.choice(["Upper respiratory infection", "Tension headache", "Essential hypertension", "Muscle strain"]),
                                 diagnosis_code=random.choice(["J06.9", "G44.2", "I10", "M62.6"]))
        Visit.objects.filter(pk=v.pk).update(created_at=when)
        m = Measurement.objects.create(patient=p, visit=v, systolic_bp=random.randint(118, 152), diastolic_bp=random.randint(76, 96),
                                       heart_rate_bpm=random.randint(64, 92), weight_kg=round(58 + i * 2.1 + random.uniform(-1.5, 1.5), 1), source="device")
        Measurement.objects.filter(pk=m.pk).update(measured_at=when)
        PrescriptionItem.objects.create(visit=v, drug=random.choice(["Paracetamol", "Amlodipine", "Ibuprofen", "Cetirizine"]), dose="500 mg", frequency="3x daily", duration="5 days")

# Today's queue.
statuses = ["completed", "completed", "in_consultation", "called", "waiting", "waiting", "waiting", "waiting", "waiting", "waiting", "waiting"]
for i, status in enumerate(statuses):
    p = patients[i]
    v = Visit.objects.create(patient=p, reason=reasons[i % len(reasons)], queue_date=today, queue_number=f"A{i + 1:03d}",
                             requested_doctor=docs[i % 3] if i % 4 else None)
    Visit.objects.filter(pk=v.pk).update(created_at=now - dt.timedelta(minutes=95 - i * 8))
    sys_bp = 186 if i == 6 else random.randint(116, 148)
    Measurement.objects.create(patient=p, visit=v, systolic_bp=sys_bp, diastolic_bp=random.randint(74, 94), heart_rate_bpm=random.randint(62, 96),
                               weight_kg=round(58 + i * 2.1, 1), source="device")
    if status != "waiting":
        doctor = docs[0] if status in ("in_consultation",) else docs[1] if status == "called" else docs[i % 3]
        queue.call(v, doctor)
        if status in ("in_consultation", "completed"):
            queue.admit(str(v.token), None)
        if status == "completed":
            v.refresh_from_db(); v.diagnosis = "Upper respiratory infection"; v.diagnosis_code = "J06.9"; v.status = Visit.COMPLETED
            v.completed_at = now; v.save()
in_progress = Visit.objects.get(queue_date=today, status=Visit.IN_CONSULTATION)
Measurement.objects.filter(visit=in_progress).update(systolic_bp=146, diastolic_bp=92, heart_rate_bpm=78, weight_kg=62.2)
in_progress.ai_summary = ("Presenting complaint:\n- Routine blood pressure check; reports mild morning headaches\nVitals today:\n"
    "- BP 146/92 mmHg (hypertension stage 2), pulse 78 bpm\n- Weight 62.2 kg, BMI 24.8\nRelevant history:\n- Hypertension, on amlodipine\n"
    "Allergies & recent medication:\n- Penicillin allergy\n- Amlodipine 5 mg once daily\nPoints to check:\n- Adherence to amlodipine and home BP readings\n- Headache pattern and red flags")
in_progress.ai_summary_model = "gpt-4o-mini"; in_progress.ai_summary_at = now; in_progress.ai_summary_by = docs[0]; in_progress.save()

# A patient with a portal account.
portal = patients[2]
user = ensure_portal_user(portal); user.set_password(PW); user.save()
portal.portal_consent_at = now; portal.save()
print("PORTAL_USER", user.username, "VISIT", in_progress.pk, "TICKET", Visit.objects.filter(queue_date=today, status="waiting").first().token)
