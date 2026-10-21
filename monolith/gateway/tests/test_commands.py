import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from aivin_gateway import store
from aivin_gateway.__main__ import CommandError, Gateway, pair_device


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
        with mock.patch(
            "aivin_gateway.__main__.pair_device", mock.AsyncMock(return_value=(paired, "HEM-6232T"))
        ) as pair:
            result = await self.gateway.cmd_pair({"address": "AA:BB:CC:DD:EE:01", "model": ""})
        pair.assert_awaited_once_with(device, None, [])
        self.assertEqual(
            result, {"address": "AA:BB:CC:DD:EE:01", "model": "HEM-6232T", "reported_model": "HEM-6232T"}
        )
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



class FakeProbe:
    def __init__(self):
        self.is_connected = True
        self.closed = False

    def release_client(self):
        return object()

    async def aclose(self):
        self.closed = True


class FakeSession:
    new_credential = None

    def __init__(self, *args, **kwargs):
        self.closed = False

    @classmethod
    def adopt(cls, client, config, pairing_session=False):
        return cls()

    def reclaim_ownership(self):
        pass

    async def connect(self):
        pass

    async def aclose(self):
        self.closed = True


class PairDeviceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(store, "DATA_DIR", data_dir),
            mock.patch.object(store, "DEVICES_FILE", data_dir / "devices.json"),
            mock.patch("aivin_gateway.__main__.OmronDeviceSession", FakeSession),
            mock.patch("aivin_gateway.__main__.async_pair_and_sync_device", mock.AsyncMock()),
            mock.patch("aivin_gateway.__main__._bluez_is_paired", mock.AsyncMock(return_value=False)),
        ]
        for p in self.patches:
            p.start()
        self.device = BLEDevice("C9:3F:DA:E0:01:4C", "BLESmart_00010412C93FDAE0014C", None)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def probe_reports(self, reported):
        self.probe = FakeProbe()
        return mock.patch(
            "aivin_gateway.__main__.async_fetch_device_model_number",
            mock.AsyncMock(return_value=(reported, self.probe)),
        )

    async def test_detected_model_wins_over_wrong_choice(self):
        # The scale advertises as "BLESmart_…" and staff picked the BP monitor.
        with self.probe_reports("HN-300T2"):
            paired, reported = await pair_device(self.device, "HEM-6232T")
        self.assertEqual((paired.model, paired.kind, reported), ("HN-300T2", "weight", "HN-300T2"))
        self.assertEqual(store.load()["C9:3F:DA:E0:01:4C"].model, "HN-300T2")

    async def test_regional_variant_resolves_to_profile(self):
        with self.probe_reports("HEM-6232T-AP"):
            paired, _ = await pair_device(self.device)
        self.assertEqual((paired.model, paired.kind), ("HEM-6232T", "bp"))

    async def test_unidentified_device_uses_chosen_model_or_asks(self):
        with self.probe_reports(None):
            with self.assertRaises(CommandError):
                await pair_device(self.device)
        self.assertTrue(self.probe.closed)
        with self.probe_reports(None):
            paired, _ = await pair_device(self.device, "HN-300T2")
        self.assertEqual(paired.model, "HN-300T2")

    async def test_unsupported_device_is_refused(self):
        with self.probe_reports("Not an Omron"):
            with self.assertRaises(CommandError):
                await pair_device(self.device)
        self.assertEqual(store.load(), {})

    async def test_old_bond_is_removed_first(self):
        fresh = BLEDevice("C9:3F:DA:E0:01:4C", "BLESmart_00010412C93FDAE0014C", None)
        with (
            mock.patch("aivin_gateway.__main__._bluez_is_paired", mock.AsyncMock(return_value=True)),
            mock.patch("aivin_gateway.__main__._bluez_remove_device", mock.AsyncMock(return_value=True)) as remove,
            mock.patch("aivin_gateway.__main__.BleakScanner.find_device_by_address", mock.AsyncMock(return_value=fresh)),
            self.probe_reports("HN-300T2") as fetch,
        ):
            await pair_device(self.device)
        remove.assert_awaited_once_with(self.device)
        self.assertIs(fetch.await_args.args[0], fresh)

    async def test_connection_failure(self):
        with mock.patch(
            "aivin_gateway.__main__.async_fetch_device_model_number", mock.AsyncMock(return_value=(None, None))
        ):
            with self.assertRaises(CommandError):
                await pair_device(self.device)


if __name__ == "__main__":
    unittest.main()
