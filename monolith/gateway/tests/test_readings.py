import datetime as dt
import unittest

from omron_ble import OmronBluetoothDeviceData

from aivin_gateway import readings


def update_for(model, *records):
    data = OmronBluetoothDeviceData(model)
    for user, record in records:
        data._update_measurement_sensors(record, user=user, multi_user=user is not None)
    return data._finish_update()


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime.now().astimezone()

    def test_blood_pressure_per_user(self):
        update = update_for(
            "HEM-6232T",
            (1, {"sys": 128, "dia": 84, "bpm": 71, "datetime": self.now}),
            (2, {"sys": 110, "dia": 70, "bpm": 60, "datetime": self.now - dt.timedelta(days=1)}),
        )
        result = sorted(readings.extract(update, "bp"), key=lambda r: r["measured_at"])
        self.assertEqual([(r["systolic"], r["diastolic"], r["heart_rate"]) for r in result], [(110, 70, 60), (128, 84, 71)])
        self.assertEqual(result[1]["measured_at"], self.now.isoformat())

    def test_weight(self):
        update = update_for("HN-300T2", (None, {"weight": 72.46, "datetime": self.now}))
        self.assertEqual(readings.extract(update, "weight"), [
            {"kind": "weight", "measured_at": self.now.isoformat(), "weight_kg": 72.5}
        ])

    def test_reading_without_timestamp_is_dropped(self):
        update = update_for("HEM-6232T", (1, {"sys": 128, "dia": 84, "bpm": 71}))
        self.assertEqual(readings.extract(update, "bp"), [])


if __name__ == "__main__":
    unittest.main()
