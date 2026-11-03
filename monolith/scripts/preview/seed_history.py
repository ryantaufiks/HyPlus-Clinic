"""Fictional past visits for the Analytics screen, and realistic waits today. Run after seed_demo.py (demo container only)."""
import datetime as dt
import random
from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone
from kiosk.models import Measurement, Patient, Visit
from kiosk.roles import DOCTOR_GROUP

random.seed(11)
docs = list(get_user_model().objects.filter(groups__name=DOCTOR_GROUP))
patients = [Patient.objects.create(name=f"Demo patient {i}") for i in range(160)]
today = timezone.localdate()
now = timezone.now()
tz = timezone.get_current_timezone()
HOURS, WEIGHTS = [8, 9, 10, 11, 17, 18, 19], [3, 6, 7, 5, 6, 7, 4]
for back in range(1, 91):
    day = today - dt.timedelta(days=back)
    for i in range(random.randint(14, 26) if day.weekday() < 5 else random.randint(5, 10)):
        t = dt.datetime.combine(day, dt.time(random.choices(HOURS, WEIGHTS)[0], random.randint(0, 59)), tzinfo=tz)
        p = random.choice(patients)
        v = Visit(patient=p, reason="Check-up", queue_date=day, queue_number=f"H{i + 1:03d}", checked_in_at=t,
                  source=random.choices([Visit.SOURCE_KIOSK, Visit.SOURCE_ONLINE], [2, 1])[0])
        outcome = random.random()
        if outcome < 0.88:
            wait, consult = random.randint(4, 30), random.randint(7, 20)
            v.status, v.doctor = Visit.COMPLETED, random.choice(docs)
            v.called_at = t + dt.timedelta(minutes=wait)
            v.started_at = v.called_at + dt.timedelta(minutes=2)
            v.completed_at = v.started_at + dt.timedelta(minutes=consult)
        else:
            v.status, v.cancel_reason = Visit.CANCELLED, random.choice(["No-show", "No-show", "Patient left"])
        v.save()
        Visit.objects.filter(pk=v.pk).update(created_at=t)
        m = Measurement.objects.create(patient=p, visit=v, systolic_bp=random.randint(104, 158), diastolic_bp=random.randint(64, 96), heart_rate_bpm=random.randint(60, 95))
        Measurement.objects.filter(pk=m.pk).update(measured_at=t + dt.timedelta(minutes=2))

# Today's tickets were all created at once by seed_demo: give them believable times.
Visit.objects.filter(queue_date=today).exclude(queue_number="").update(checked_in_at=F("created_at"))
for v in Visit.objects.filter(queue_date=today, called_at__isnull=False):
    Visit.objects.filter(pk=v.pk).update(called_at=v.checked_in_at + dt.timedelta(minutes=random.randint(10, 24)))
print("HISTORY seeded")
