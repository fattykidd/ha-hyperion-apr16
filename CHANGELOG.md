# Changelog

All notable changes to this integration are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Earlier releases are listed on the
[releases page](https://github.com/fattykidd/ha-hyperion-apr16/releases).

## [0.3.5] - 2026-11-21

### Added

- **Live updates.** The integration follows the processor's own state streams (audio, inputs, Dirac, speakers
  and video), so volume, mute, power, the Dirac slot and state, loudness and the video signal update within a
  fraction of a second, including changes made on the processor's web page.
- **Loudness** switch. It is unavailable on firmware that doesn't offer loudness.
- **Maximum Volume** and **Power-On Volume** controls, listed under the device's configuration.
- **Video Format** sensor (resolution and refresh rate, or `No Signal`) and **HDR Status** sensor.
- **Dirac Live** support: a **Dirac Filter Slot** select, a **Dirac Active** switch that shows and sets the real
  filtering state, **Dirac Enable** and **Dirac Disable** buttons, one button per Dirac slot, and an **Active
  Dirac Slot** sensor.
- The media player's source list uses the custom names you gave your inputs on the processor.

### Changed

- Polling is now the fallback. While live updates are connected, the full status is re-read every 30 seconds as a
  safety net (and straight after you change something), instead of every 5 seconds. If live updates are not
  available, the integration polls every 5 seconds as before.
- The **Video Signal** sensor updates live.
- Firmware version and MAC address are read once instead of on every update.
- The integration is now classed as `local_push`.
- Input names are read for inputs 1 to 16 (previously 1 to 8 in one place and 1 to 16 in another).

### Internal

- Requests use `aiohttp` timeout objects instead of bare numbers.
- New automated tests for the live streams, the coordinator, the Dirac and loudness switches, the volume controls,
  the video sensors and the device client.
- The test workflow runs on Python 3.14 with `tzdata`, matching what Home Assistant's test tools require.
- The release workflow checks that a stable tag matches the manifest version and has a changelog entry, and
  publishes tags containing a `-` (such as `v0.3.6-beta`) as pre-releases so HACS does not offer them to
  stable users.
