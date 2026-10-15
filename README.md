# Halo Collar

Unofficial Home Assistant integration for a [Halo Collar](https://www.halocollar.com/) account. It signs in with your Halo email and password, then polls location and collar state. It does not send commands.

This project is not affiliated with, endorsed by, or supported by Halo Collar.

## Credit

The Halo HTTP API used here was documented by [sevenlayercookie](https://github.com/sevenlayercookie) in [halo-collar-api](https://github.com/sevenlayercookie/halo-collar-api). That project is an unofficial Python client for the Halo Collar REST and SignalR APIs. This integration reimplements the Android password login and the read calls it needs. It does not include that client's write APIs, corrections, fence edits, or live SignalR stream.

## What it adds

One Home Assistant device per pet:

- Device tracker with the collar's last GPS fix, so Home Assistant zones work
- Battery, connection (Wi-Fi, cellular, or offline), current geofence, and last telemetry time
- Fences on, beacons on, walk in progress, and online
- Configuration sync, firmware update status, and a read-only firmware entity
- Recent corrections count from the account map, when Halo attributes them to a pet

Pets without a collar still appear, with their entities unavailable.

## What it does not do

There are no actions. The integration never calls Halo with POST, PUT, PATCH, or DELETE except the OAuth token request used to sign in and refresh a session. It cannot send a correction, change fences, start or stop a walk, locate the collar, or install firmware.

The default poll reads the last location Halo already has. Turn on **Ask the collar for fresh telemetry** only if you want each poll to wake the collar.

## Install

[HACS](https://hacs.xyz/) custom repository:

1. HACS → Integrations → menu → Custom repositories
2. Add `https://github.com/KyleTeal/ha-halo-collar` as category **Integration**
3. Install **Halo Collar** and restart Home Assistant
4. Settings → Devices & services → Add Integration → Halo Collar

The password is sent to `https://auth.halocollar.com` and is not written to the config entry. Home Assistant stores the refresh token. If Halo rejects that token later, Home Assistant asks for the password again.

## Options

- **Update interval:** 60 to 900 seconds. Default 120.
- **Ask the collar for fresh telemetry:** off by default.

## Privacy

Diagnostics redact the email, tokens, app instance id, collar serial, and coordinates. Dog names stay so the file is usable. Do not share an unredacted debug log; telemetry can contain a precise location.
