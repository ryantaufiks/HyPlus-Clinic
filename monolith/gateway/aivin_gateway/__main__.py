"""AIVIN BLE gateway.

Listens for OMRON advertisements on the host's Bluetooth adapter, reads new
measurements with the vendored omron_ble protocol library, and posts them to
the AIVIN web app.

    python -m aivin_gateway run
    python -m aivin_gateway scan [--seconds 20]
    python -m aivin_gateway pair --address AA:BB:... --model HEM-6232T
    python -m aivin_gateway list
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

import httpx
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from omron_ble import OmronBluetoothDeviceData
from omron_ble.devices import get_device_config
from omron_ble.pairing import async_pair_and_sync_device
from omron_ble.session import OmronDeviceSession

from . import readings, store

log = logging.getLogger("aivin_gateway")

AIVIN_URL = os.environ.get("AIVIN_URL", "http://web:8000").rstrip("/")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
HEARTBEAT_SECONDS = 3
# A device that is advertising while the kiosk waits for it is polled at most this often.
POLL_COOLDOWN_SECONDS = 15
POLL_TIMEOUT_SECONDS = 180

OMRON_MANUFACTURER_ID = 526


def service_info(device: BLEDevice, adv: AdvertisementData) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name=adv.local_name or device.name or device.address,
        address=device.address,
        rssi=adv.rssi,
        manufacturer_data=adv.manufacturer_data,
        service_data=adv.service_data,
        service_uuids=adv.service_uuids,
        source="local",
        device=device,
        advertisement=adv,
        connectable=True,
        time=time.monotonic(),
        tx_power=adv.tx_power,
    )


class AivinClient:
    def __init__(self) -> None:
        # Host header must be in the web app's ALLOWED_HOSTS; X-Forwarded-Proto
        # keeps its HTTPS redirect from bouncing internal calls.
        self._http = httpx.AsyncClient(
            base_url=AIVIN_URL,
            timeout=10,
            headers={
                "Authorization": f"Bearer {GATEWAY_TOKEN}",
                "Host": "localhost",
                "X-Forwarded-Proto": "https",
            },
        )

    async def heartbeat(self, devices: list[dict]) -> list[str]:
        response = await self._http.post("/internal/gateway/heartbeat/", json={"devices": devices})
        response.raise_for_status()
        return response.json().get("waiting", [])

    async def post_reading(self, address: str, model: str, reading: dict) -> None:
        response = await self._http.post(
            "/internal/device-readings/",
            json={"device_address": address, "device_model": model, **reading},
        )
        response.raise_for_status()


class Gateway:
    def __init__(self) -> None:
        self.devices = store.load()
        self.client = AivinClient()
        self.data: dict[str, OmronBluetoothDeviceData] = {}
        for address, paired in self.devices.items():
            data = OmronBluetoothDeviceData(paired.model)
            if paired.credential_hex:
                data.transport_credential = bytes.fromhex(paired.credential_hex)
            self.data[address] = data
        self.last_seen: dict[str, float] = {}
        self.last_poll: dict[str, float] = {}
        self.waiting: set[str] = set()
        self.ble_lock = asyncio.Lock()

    def on_advertisement(self, device: BLEDevice, adv: AdvertisementData) -> None:
        address = device.address.upper()
        paired = self.devices.get(address)
        if paired is None:
            return
        self.last_seen[address] = time.time()
        data = self.data[address]
        try:
            data.update(service_info(device, adv))
        except Exception:
            log.exception("Could not parse advertisement from %s", address)
            return

        forced = bool(getattr(data, "forced_transfer", False))
        wanted = paired.kind in self.waiting
        recently = time.time() - self.last_poll.get(address, 0) < POLL_COOLDOWN_SECONDS
        if (forced or wanted) and not recently and not self.ble_lock.locked():
            self.last_poll[address] = time.time()
            asyncio.get_running_loop().create_task(self.poll(address, device, forced))

    async def poll(self, address: str, device: BLEDevice, forced: bool) -> None:
        paired = self.devices[address]
        data = self.data[address]
        async with self.ble_lock:
            log.info("Polling %s %s (forced_transfer=%s)", paired.model, address, forced)
            try:
                async with asyncio.timeout(POLL_TIMEOUT_SECONDS):
                    update = await data.async_poll(device)
            except Exception as exc:
                log.warning("Poll of %s failed: %s", address, exc)
                return
        if data.pending_credential is not None:
            paired.credential_hex = data.pending_credential.hex()
            data.pending_credential = None
            store.save(self.devices)
        for reading in readings.extract(update, paired.kind):
            try:
                await self.client.post_reading(address, paired.model, reading)
                log.info("Posted %s reading measured at %s", reading["kind"], reading["measured_at"])
            except httpx.HTTPError as exc:
                log.warning("Could not post reading: %s", exc)

    async def heartbeat_loop(self) -> None:
        while True:
            status = [
                {
                    "address": address,
                    "model": paired.model,
                    "kind": paired.kind,
                    "last_seen": self.last_seen.get(address),
                }
                for address, paired in self.devices.items()
            ]
            try:
                self.waiting = set(await self.client.heartbeat(status))
            except httpx.HTTPError as exc:
                log.warning("Heartbeat failed: %s", exc)
            await asyncio.sleep(HEARTBEAT_SECONDS)

    async def run(self) -> None:
        if not GATEWAY_TOKEN:
            sys.exit("GATEWAY_TOKEN is not set")
        if not self.devices:
            log.warning("No paired devices yet. Pair one with: python -m aivin_gateway pair ...")
        scanner = BleakScanner(detection_callback=self.on_advertisement, scanning_mode="active")
        await scanner.start()
        log.info("Gateway running; %d paired device(s)", len(self.devices))
        try:
            await self.heartbeat_loop()
        finally:
            await scanner.stop()


async def cmd_scan(seconds: float) -> None:
    print(f"Scanning {seconds:.0f}s for OMRON devices (put the device in pairing mode: hold Bluetooth until -P- blinks)...")
    found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    for device, adv in found.values():
        name = adv.local_name or device.name or ""
        if OMRON_MANUFACTURER_ID in adv.manufacturer_data or name.startswith(("HEM-", "HN-", "BLEsmart", "BLESmart")):
            print(f"{device.address}  rssi={adv.rssi:>4}  {name}")


async def cmd_pair(address: str, model: str) -> None:
    address = address.upper()
    kind = store.KIND_BY_MODEL.get(model)
    if kind is None:
        sys.exit(f"Unsupported model {model}; supported: {', '.join(store.KIND_BY_MODEL)}")
    device = await BleakScanner.find_device_by_address(address, timeout=30)
    if device is None:
        sys.exit(f"{address} not found. Is the device in pairing mode (-P- blinking)?")

    session = OmronDeviceSession(device, get_device_config(model), pairing_session=True)
    try:
        await session.connect()
        await async_pair_and_sync_device(session, model)
        credential = session.new_credential
    finally:
        await session.aclose()

    devices = store.load()
    devices[address] = store.PairedDevice(
        address=address, model=model, kind=kind, credential_hex=credential.hex() if credential else None
    )
    store.save(devices)
    print(f"Paired {model} {address}. Restart the gateway to start reading it: make restart-gateway")


def cmd_list() -> None:
    for paired in store.load().values():
        print(f"{paired.address}  {paired.model}  ({paired.kind})")


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # One request every few seconds; only failures are interesting.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="aivin_gateway")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run")
    scan = sub.add_parser("scan")
    scan.add_argument("--seconds", type=float, default=20)
    pair = sub.add_parser("pair")
    pair.add_argument("--address", required=True)
    pair.add_argument("--model", required=True, choices=sorted(store.KIND_BY_MODEL))
    sub.add_parser("list")
    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(Gateway().run())
    elif args.command == "scan":
        asyncio.run(cmd_scan(args.seconds))
    elif args.command == "pair":
        asyncio.run(cmd_pair(args.address, args.model))
    elif args.command == "list":
        cmd_list()


if __name__ == "__main__":
    main()
