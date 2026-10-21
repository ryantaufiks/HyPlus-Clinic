# AIVIN — AI-Vital Intake

**Kiosk pemeriksaan tanda vital mandiri untuk tahap pra-konsultasi.**

Before a patient sees the doctor, a nurse usually measures their vital signs, writes them down, and passes the notes on to the doctor. AIVIN takes over this intake step: an AI voice assistant guides the patient, Bluetooth medical devices take the measurements, everything is recorded automatically, and the doctor receives the results ready for further examination. The goal is to **reduce nurse workload**, not to replace nurses.

## Features

- Voice-guided patient intake (Web Speech API)
- OMRON HEM-6232T blood-pressure monitor and HN-300T2 scale, read automatically by a BLE gateway on the server
- Queue tickets with QR codes; doctors scan the QR to open the patient's results
- Staff dashboard, patient records and measurement history (login required)
- Admin-managed system settings, with the OpenAI API key stored encrypted

## Architecture

| Component | Technology |
|---|---|
| App | Django 5.2 served by Gunicorn, static files by WhiteNoise |
| Database | PostgreSQL 16 |
| Runtime | Docker Compose (`aivin` project), app port bound to `127.0.0.1` only |
| Devices | BLE gateway on the server's Bluetooth adapter (BlueZ) |
| Public access | Cloudflare Tunnel (`cloudflared`) terminates HTTPS |
| Android | Capacitor wrapper that loads the hosted app |

```
Browser / tablet ──HTTPS──> Cloudflare ──tunnel──> cloudflared (host) ──> 127.0.0.1:8010 ──> web (Gunicorn) ──> db (PostgreSQL)
```

Who can see what:

- **Public:** the kiosk screen (`/`) and its intake API. The API is CSRF-protected and rate-limited.
- **Login required:** dashboard, patients, QR scanner and tickets.
- **Superuser only:** Admin → System settings.

## Deploying on Debian

Requirements: Docker Engine with the Compose plugin, `make`, `python3`, and a running Cloudflare Tunnel.

```bash
cd monolith
make init-env          # creates .env with generated SECRET_KEY, FIELD_ENCRYPTION_KEY and DB password
make up                # builds the image, starts db + web, runs migrations
make createsuperuser   # first administrator account (interactive)
```

Then, in the Cloudflare Zero Trust dashboard, add a public hostname to the tunnel (for example `aivin.sc2platform.biz.id`) pointing to `http://localhost:8010`. The hostname must be listed in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in `.env`. Run `make restart` after editing `.env`.

Check that the app is up: `curl http://127.0.0.1:8010/healthz/` should return `{"status": "ok"}`.

## Patients, registration and doctors

- **Patient ID**: every patient gets a 5-character ID (e.g. `K7M2Q`), shown on the kiosk ticket. Returning patients choose *I have a Patient ID* at the kiosk.
- **Ticket QR code** links to `PUBLIC_BASE_URL/v/<token>/`. Staff who scan it while signed in open the visit. A patient who scans it with their phone gets a form to complete their registration. The form never shows stored data, expires after 7 days, and its answers wait in **Registrations** until staff approve them.
- **Staff accounts** are managed by administrators under **Staff** (or *Add staff member* on Registrations). Roles:
  - *Doctor*: records diagnoses and prescriptions.
  - *Nurse*: also manages the OMRON devices and merges duplicate records.
  - *Front desk*: registers patients and reviews registrations.
  - *Administrator*: everything, including staff accounts.

  Each role only sees the menus it can use, and the server refuses the rest (doctors, for example, have no Kiosk, Registrations or Scan ticket pages).

  Administrators never set passwords: a new account (or a reset) gives a one-time setup link, valid 3 days, to send to the staff member. Accounts are deactivated, not deleted, so records keep their author.
- Prescriptions are checked by name against the patient's recorded drug allergies; cross-reactivity between drug classes is not detected.
- Only the last 4 characters of an ID document are stored. Changes to registration and medical data are recorded in an audit log shown on each patient's page.

## Queue, TV display and access control

1. The kiosk prints (or shows) the ticket: queue number, Patient ID and QR code. Patients who scan it on their phone see their place in the queue, can save the QR code and complete their registration.
2. The waiting-room TV opens `/display/` (no login; it shows queue numbers and rooms only). Tap once to enable the chime. It lists every doctor on duty with their room (In progress, Called or Available); doctors switch **On duty / Off duty** on the Consultations page.
3. A doctor presses **Call next** (or **Call** on a patient) under Consultations. The TV plays a chime and shows the number and the doctor's room. Each doctor's room is set under **Staff**.
4. At the consulting-room door, staff scan the ticket under **Scan ticket** (access control). It turns green only for called patients, and the visit becomes **In progress** on the TV and on the doctor's screen.
5. The doctor records the diagnosis and prescription and presses **Complete & call next**; the TV moves on to the next number. Critical blood pressure is called first.
6. Doctors, nurses and administrators can **cancel** a queued visit (no-show, patient left, duplicate…). A reason is required. The visit leaves the queue and the TV but is never deleted: its record, vitals, the reason and who cancelled it are kept.

## Medical devices (OMRON)

Supported: **HEM-6232T** wrist blood-pressure monitor and **HN-300T2** scale. They are read by the BLE gateway (`monolith/gateway`) on the server's own Bluetooth adapter, so **the devices must be within Bluetooth range of the server** (same room, roughly 5–10 m). Tablets and phones only need a browser.

The protocol implementation is vendored from [eigger/hass-omron](https://github.com/eigger/hass-omron) (MIT). Its HN-300T2 support is marked beta upstream.

Pair each device once, from **Devices** in the navbar (staff login):

1. Remove the device from the OMRON connect app / phone Bluetooth settings first. A device talks to one host at a time.
2. Hold the device's Bluetooth button until `-P-` blinks, click **Scan**, choose the model and click **Pair**. The device shows `OK` when it worked.
3. Use **Test connection** (press the device's Bluetooth button first to wake it). It reads the latest stored measurement without saving it to any patient.

The same is available from the terminal: `make devices-scan`, `make devices-pair ADDRESS=... MODEL=HEM-6232T`, `make devices-list`.

During a check-in, the kiosk's weight and blood-pressure steps wait for the device and show the result automatically. Readings are only accepted if the device timestamp is after the step started; the gateway keeps the device clocks in sync. Check the gateway with `make gateway-logs`.

Simulated measurements (random values) are only available with `DEBUG=true`, and are stored with source "simulated".

## Secrets and configuration

| Secret | Where it lives | How to change it |
|---|---|---|
| OpenAI API key | Database, Fernet-encrypted | **Admin → System settings**. The field is write-only: the stored key is never shown again, only a hint like `sk-…abcd`. |
| `SECRET_KEY` | `monolith/.env` (mode 600) | Generated by `make init-env`. Edit `.env` and run `make restart`. This signs everyone out. |
| `FIELD_ENCRYPTION_KEY` | `monolith/.env` | Generated by `make init-env`. **Back it up.** If it is lost or changed, stored secrets cannot be decrypted and must be entered again. |
| Database password | `monolith/.env` | Generated by `make init-env`. |

`SECRET_KEY` and `FIELD_ENCRYPTION_KEY` deliberately cannot be edited from the web UI. Django needs them before it can read the database, and changing them from a web form would let one compromised admin session lock out or sign out everyone.

Application code reads the OpenAI key with `kiosk.models.get_openai_api_key()`.

All other settings are documented in [`monolith/.env.example`](monolith/.env.example).

## Operations

Run these commands from `monolith/`:

| Command | What it does |
|---|---|
| `make ps` / `make logs` | Container status and app logs |
| `make up` | Rebuild and redeploy after pulling new code (migrations run automatically) |
| `make backup` | Write a gzipped `pg_dump` to `monolith/backups/` (git-ignored) |
| `make restore FILE=backups/<file>.sql.gz` | Restore a dump |
| `make down` | Stop the stack. Data is kept in the `aivin_pgdata` volume. |

Schedule `make backup` (for example a daily cron job), and copy the backups and `.env` off the server.

## Development

```bash
make test        # run the test suite inside the container, against PostgreSQL
```

To run without Docker, create a virtualenv, install `monolith/requirements.txt`, set `DEBUG=true` in `.env`, and leave out the `POSTGRES_*` variables so SQLite is used. Then run `python manage.py migrate` and `python manage.py runserver`.

## More documentation

- [docs/device-testing.md](docs/device-testing.md): testing with real Omron Bluetooth devices
- [docs/legacy/](docs/legacy/): notes from the earlier Windows-based setup. They are kept for reference and are not maintained.
