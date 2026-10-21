"""Turn an omron_ble SensorUpdate into AIVIN device readings."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

_KEY = re.compile(
    r"^(?P<field>blood_pressure_systolic|blood_pressure_diastolic|heart_rate|weight|measurement_timestamp)"
    r"(?P<user>_[a-z0-9_]+)?$"
)
_FIELD_NAMES = {
    "blood_pressure_systolic": "systolic",
    "blood_pressure_diastolic": "diastolic",
    "heart_rate": "heart_rate",
    "weight": "weight_kg",
    "measurement_timestamp": "measured_at",
}


def extract(update: Any, kind: str) -> list[dict[str, Any]]:
    """One reading per device user that has a complete, timestamped record.

    Readings without a device timestamp are dropped: without it the server
    cannot tell a fresh measurement from an old record still in memory.
    """
    groups: dict[str, dict[str, Any]] = {}
    for device_key, value in update.entity_values.items():
        match = _KEY.match(device_key.key)
        if not match or value.native_value is None:
            continue
        groups.setdefault(match["user"] or "", {})[_FIELD_NAMES[match["field"]]] = value.native_value

    readings = []
    for values in groups.values():
        measured_at = values.get("measured_at")
        if not isinstance(measured_at, dt.datetime):
            continue
        if kind == "bp" and values.get("systolic") is not None and values.get("diastolic") is not None:
            readings.append(
                {
                    "kind": "bp",
                    "measured_at": measured_at.isoformat(),
                    "systolic": int(values["systolic"]),
                    "diastolic": int(values["diastolic"]),
                    "heart_rate": int(values["heart_rate"]) if values.get("heart_rate") is not None else None,
                }
            )
        elif kind == "weight" and values.get("weight_kg") is not None:
            readings.append(
                {
                    "kind": "weight",
                    "measured_at": measured_at.isoformat(),
                    "weight_kg": round(float(values["weight_kg"]), 1),
                }
            )
    return readings
