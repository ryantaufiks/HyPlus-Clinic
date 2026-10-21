"""Clinical interpretation of measurements, shared by the dashboard, patient
pages and the doctor's ticket."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BpCategory:
    key: str
    label: str
    status: str  # design-system status: good / warning / serious / critical
    icon: str


# ACC/AHA 2017 adult blood-pressure categories, mildest first.
BP_CATEGORIES = [
    BpCategory("normal", "Normal", "good", "bi-check-circle-fill"),
    BpCategory("elevated", "Elevated", "warning", "bi-exclamation-circle-fill"),
    BpCategory("stage1", "Hypertension stage 1", "serious", "bi-exclamation-triangle-fill"),
    BpCategory("stage2", "Hypertension stage 2", "critical", "bi-exclamation-octagon-fill"),
    BpCategory("crisis", "Hypertensive crisis", "critical", "bi-exclamation-octagon-fill"),
]
_BY_KEY = {c.key: c for c in BP_CATEGORIES}


def bp_category(systolic, diastolic):
    """The ACC/AHA category for a reading, or None when it is incomplete."""
    if systolic is None or diastolic is None:
        return None
    if systolic > 180 or diastolic > 120:
        key = "crisis"
    elif systolic >= 140 or diastolic >= 90:
        key = "stage2"
    elif systolic >= 130 or diastolic >= 80:
        key = "stage1"
    elif systolic >= 120:
        key = "elevated"
    else:
        key = "normal"
    return _BY_KEY[key]


def heart_rate_status(bpm):
    """Resting adult heart rate: 60–100 bpm is normal."""
    if bpm is None:
        return None
    if bpm < 50 or bpm > 120:
        return BpCategory("hr", "Out of range", "critical", "bi-exclamation-octagon-fill")
    if bpm < 60 or bpm > 100:
        return BpCategory("hr", "Borderline", "warning", "bi-exclamation-circle-fill")
    return BpCategory("hr", "Normal", "good", "bi-check-circle-fill")
