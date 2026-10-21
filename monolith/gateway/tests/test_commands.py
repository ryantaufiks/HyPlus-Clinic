import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from aivin_gateway import store
from aivin_gateway.__main__ import CommandError, Gateway


def advertisement(name="HEM-6232T", rssi=-60):
    return AdvertisementData(
        local_name=name,
        manufacturer_data={526: b"\x01\x00"},
        service_data={},
        service_uuids=[],
        tx_power=None,
        rssi=rssi,
        platform_data=(),
    )


class GatewayCommandTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(store, "DATA_DIR", data_dir),
            mock.patch.object(store, "DEVICES_FILE", data_dir / "devices.json"),
        ]
        for p in self.patches:
            p.start()
        self.gateway = Gateway()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    async def test_scan_reports_nearby_omron_devices_only(self):
        self.gateway.on_advertisement(BLEDevice("AA:BB:CC:DD:EE:01", "HEM-6232T", None), advertisement())
        other = AdvertisementData(
            local_name="Headphones", manufacturer_data={76: b"\x00"}, service_data={},
            service_uuids=[], tx_power=None, rssi=-50, platform_data=(),
        )
        self.gateway.on_advertisement(BLEDevice("AA:BB:CC:DD:EE:02", "Headphones", None), other)
        result = await self.gateway.cmd_scan({"seconds": 0})
        self.assertEqual([d["address"] for d in result["devices"]], ["AA:BB:CC:DD:EE:01"])
        self.assertFalse(result["devices"][0]["paired"])

    async def test_pair_requires_device_nearby(self):
        with self.assertRaises(CommandError):
            await self.gateway.cmd_pair({"address": "AA:BB:CC:DD:EE:01", "model": "HEM-6232T"})

    async def test_pair_registers_device_without_restart(self):
        device = BLEDevice("AA:BB:CC:DD:EE:01", "HEM-6232T", None)
        self.gateway.on_advertisement(device, advertisement())
        paired = store.PairedDevice(address="AA:BB:CC:DD:EE:01", model="HEM-6232T", kind="bp")
        with mock.patch("aivin_gateway.__main__.pair_device", mock.AsyncMock(return_value=paired)) as pair:
            result = await self.gateway.cmd_pair({"address": "AA:BB:CC:DD:EE:01", "model": "HEM-6232T"})
        pair.assert_awaited_once_with(device, "HEM-6232T")
        self.assertEqual(result, {"address": "AA:BB:CC:DD:EE:01", "model": "HEM-6232T"})
        self.assertIn("AA:BB:CC:DD:EE:01", self.gateway.devices)
        self.assertIn("AA:BB:CC:DD:EE:01", self.gateway.data)

    async def test_test_and_remove_require_paired_device(self):
        with self.assertRaises(CommandError):
            await self.gateway.cmd_test({"address": "AA:BB:CC:DD:EE:01"})
        with self.assertRaises(CommandError):
            await self.gateway.cmd_remove({"address": "AA:BB:CC:DD:EE:01"})

    async def test_remove_forgets_device(self):
        paired = store.PairedDevice(address="AA:BB:CC:DD:EE:01", model="HN-300T2", kind="weight")
        store.save({paired.address: paired})
        self.gateway.register(paired)
        await self.gateway.cmd_remove({"address": paired.address})
        self.assertEqual(store.load(), {})
        self.assertNotIn(paired.address, self.gateway.devices)

    async def test_test_times_out_when_device_asleep(self):
        paired = store.PairedDevice(address="AA:BB:CC:DD:EE:01", model="HEM-6232T", kind="bp")
        self.gateway.register(paired)
        with mock.patch("aivin_gateway.__main__.TEST_WAIT_SECONDS", 0):
            with self.assertRaises(CommandError):
                await self.gateway.cmd_test({"address": paired.address})


if __name__ == "__main__":
    unittest.main()
