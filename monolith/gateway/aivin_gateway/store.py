"""Paired-device registry, persisted as JSON in the gateway's data volume."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from omron_ble.devices import CANONICAL_DEVICE_PROFILES, MeasurementKind, get_device_config

DATA_DIR = Path(os.environ.get("GATEWAY_DATA_DIR", "/data"))
DEVICES_FILE = DATA_DIR / "devices.json"

# The models this kiosk is set up with; staff can pick them when auto-detection fails.
KIND_BY_MODEL = {
    "HEM-6232T": "bp",
    "HN-300T2": "weight",
}


def kind_for_model(model: str) -> str | None:
    """"bp" or "weight" for any OMRON profile in the vendored catalog, else None."""
    if model not in CANONICAL_DEVICE_PROFILES:
        return None
    measured = get_device_config(model).measurement_kind
    if measured == MeasurementKind.BLOOD_PRESSURE:
        return "bp"
    if measured in (MeasurementKind.WEIGHT, MeasurementKind.BODY_COMPOSITION):
        return "weight"
    return None


@dataclass
class PairedDevice:
    address: str
    model: str
    kind: str
    # Application-layer credential some OMRON profiles establish at pairing.
    credential_hex: str | None = None


def load() -> dict[str, PairedDevice]:
    if not DEVICES_FILE.exists():
        return {}
    raw = json.loads(DEVICES_FILE.read_text())
    return {d["address"].upper(): PairedDevice(**d) for d in raw}


def save(devices: dict[str, PairedDevice]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DEVICES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(d) for d in devices.values()], indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(DEVICES_FILE)
