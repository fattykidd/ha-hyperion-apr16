"""Data update coordinator for AudioControl Hyperion APR-16."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FULL_REFRESH_INTERVAL, POLL_INTERVAL, STREAM_KINDS
from .helper import percent_to_db
from .stream import StateStream

_LOG = logging.getLogger(__name__)

# What the audio stream reports that maps one-to-one onto this integration's data.
_AUDIO_FIELDS = {"power": bool, "mute": bool}

# The volume limits are reported by the audio stream under the processor's names; data uses ours.
_AUDIO_LIMIT_FIELDS = {"max_volume": "max_volume", "on_volume": "power_on_volume"}

# Fields of the audio stream that change what the REST status would say. Seeing one change means the
# status is re-read, rather than guessing how the stream's wording maps onto the REST wording.
_AUDIO_REFRESH_FIELDS = ("audio_mode", "audio_format", "bit_depth", "sample_rate")


class HyperionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Keeps the processor's state up to date.

    The processor pushes its changes over WebSockets, so while those are connected the state is updated the
    moment something changes and the REST status is only re-read every FULL_REFRESH_INTERVAL seconds, as a
    safety net. If the streams are not available (older firmware, processor rebooting) it polls every
    POLL_INTERVAL seconds, as it always did.
    """

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOG,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.device = device
        self._streams: list[StateStream] = []
        self._last_full_refresh = 0.0  # monotonic
        self._force_refresh = True
        self._refresh_task: asyncio.Task | None = None
        self._refresh_again = False
        self._last_audio_state: dict[str, Any] | None = None
        self._last_inputs_state: dict[str, Any] | None = None
        self._pushed: dict[str, Any] = {}  # values only the streams report: a REST refresh must not lose them
        self._static: dict[str, Any] = {}  # firmware and MAC address: read once, they don't change

    # ------------------------------------------------------------------ live streams

    @property
    def streams_live(self) -> bool:
        """True while every stream is connected, so the pushed state can be trusted."""
        return bool(self._streams) and all(stream.live for stream in self._streams)

    def async_start_streams(self) -> None:
        """Start following the processor's live state."""
        handlers = {
            "audio": self._on_audio_state,
            "inputs": self._on_inputs_state,
            "dirac": self._on_dirac_state,
            "speakers": self._on_speakers_state,
        }
        for kind in STREAM_KINDS:
            stream = StateStream(
                kind,
                self.device.async_open_state_stream,
                handlers[kind],
                log_id=getattr(self.device, "host", "") or "",
            )
            self._streams.append(stream)
            stream.start()

    async def async_stop_streams(self) -> None:
        """Stop following the processor."""
        streams, self._streams = self._streams, []
        for stream in streams:
            await stream.stop()
        task, self._refresh_task = self._refresh_task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def _on_audio_state(self, state: dict[str, Any]) -> None:
        """The processor reported its audio state: apply what it says now, re-read what it doesn't."""
        if self.data is None:
            return
        data = dict(self.data)
        changed = False

        for key, kind in _AUDIO_FIELDS.items():
            if isinstance(state.get(key), kind) and data.get(key) != state[key]:
                data[key] = state[key]
                changed = True

        volume = state.get("volume")
        is_number = isinstance(volume, (int, float)) and not isinstance(volume, bool)
        if is_number and data.get("volume") != float(volume):
            data["volume"] = float(volume)
            data["volume_db"] = round(percent_to_db(float(volume)), 1)
            changed = True

        for stream_key, key in _AUDIO_LIMIT_FIELDS.items():
            limit = state.get(stream_key)
            if isinstance(limit, (int, float)) and not isinstance(limit, bool) and data.get(key) != float(limit):
                data[key] = float(limit)
                changed = True

        if changed:
            self.async_set_updated_data(data)

        previous, self._last_audio_state = self._last_audio_state, state
        if previous is not None and any(
            state.get(field) != previous.get(field) for field in _AUDIO_REFRESH_FIELDS
        ):
            self._schedule_full_refresh()

    def _on_inputs_state(self, state: dict[str, Any]) -> None:
        """The active input changed (or the processor just told us which it is): re-read everything about it."""
        previous, self._last_inputs_state = self._last_inputs_state, state
        if previous is not None:
            self._schedule_full_refresh()

    def _on_dirac_state(self, state: dict[str, Any]) -> None:
        """The Dirac slot or filtering changed on the processor (or in its web UI)."""
        if self.data is None:
            return

        changes: dict[str, Any] = {}
        slot = state.get("active_slot")
        if isinstance(slot, int) and not isinstance(slot, bool):
            changes["active_slot"] = slot
        filtering = state.get("filtering_enabled")
        if isinstance(filtering, bool):
            changes["dirac_active"] = filtering

        if any(self.data.get(key) != value for key, value in changes.items()):
            self.async_set_updated_data({**self.data, **changes})

    def _on_speakers_state(self, state: dict[str, Any]) -> None:
        """The speaker set-up changed. Only the loudness setting is used; the stream is its only source."""
        changes: dict[str, Any] = {}
        capability = state.get("loudness_capability")
        if isinstance(capability, str):
            changes["loudness_supported"] = capability == "supported"
        enabled = state.get("loudness_enabled")
        if isinstance(enabled, bool):
            changes["loudness"] = enabled
        self.async_apply_pushed(changes)

    def async_apply_pushed(self, changes: dict[str, Any]) -> None:
        """Take values that only a stream can report, and keep them across REST refreshes."""
        if not changes:
            return
        self._pushed.update(changes)
        if self.data is not None and any(self.data.get(key) != value for key, value in changes.items()):
            self.async_set_updated_data({**self.data, **changes})

    def _schedule_full_refresh(self) -> None:
        """Re-read the whole status now, once, however many changes arrive meanwhile."""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_again = True  # the refresh under way may already have missed this change
            return
        self._refresh_task = self.hass.async_create_background_task(
            self._refresh_until_settled(), name="hyperion-apr16-refresh"
        )

    async def _refresh_until_settled(self) -> None:
        while True:
            self._refresh_again = False
            self._force_refresh = True
            await self.async_refresh()
            if not self._refresh_again:
                return

    # ------------------------------------------------------------------ polling

    async def async_request_refresh(self) -> None:
        """Re-read the whole status. Entities call this after sending a command."""
        self._force_refresh = True
        await super().async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Hyperion APR-16 processor."""
        if (
            not self._force_refresh
            and self.data is not None
            and self.streams_live
            and time.monotonic() - self._last_full_refresh < FULL_REFRESH_INTERVAL
        ):
            return self.data  # the streams have kept it current

        self._force_refresh = False
        try:
            data = await self._async_fetch_status()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Hyperion APR-16: {err}") from err

        self._last_full_refresh = time.monotonic()
        return {**data, **self._pushed}

    async def _async_fetch_status(self) -> dict[str, Any]:
        """Read the whole status over REST."""
        # Fetch base status dict directly from the Apr16 client in device.py
        data = await self.device.async_get_status()

        # The active Dirac slot, read live from the processor
        data["active_slot"] = await self.device.async_get_dirac_active_slot()

        # Whether Dirac filtering is on. If it can't be read this time, keep what we knew.
        filtering = await self.device.async_get_dirac_filtering()
        data["dirac_active"] = filtering if filtering is not None else (self.data or {}).get("dirac_active")

        _LOG.debug("RAW async_get_status Payload -> keys: %s | full_data: %r", list(data), data)

        # Attach device property metadata
        data["host_ip"] = getattr(self.device, "host", None)

        # Calculate volume dB
        vol_val = data.get("volume", data.get("level", 0.0))
        if vol_val is not None:
            data["volume_db"] = round(percent_to_db(float(vol_val)), 1)

        # Get the current active input ID (fallback to 1 if not present)
        input_id = data.get("input_id", data.get("active_input_id", 1))
        data["input_id"] = input_id

        # Fetch live per-input audio settings from GET endpoints safely
        try:
            trim_resp = await self.device.async_get_trim(input_id)
            data["channel_trim"] = float(trim_resp.get("level", 0))
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("Could not fetch channel trim for input %s: %s", input_id, err)

        try:
            gain_resp = await self.device.async_get_gain(input_id)
            data["channel_gain"] = float(gain_resp.get("level", 0))
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("Could not fetch channel gain for input %s: %s", input_id, err)

        try:
            lipsync_resp = await self.device.async_get_lipsync(input_id)
            data["lipsync_delay"] = float(lipsync_resp.get("delayMs", 0))
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("Could not fetch lipsync delay for input %s: %s", input_id, err)

        for key, read in (
            ("max_volume", self.device.async_get_max_volume),
            ("power_on_volume", self.device.async_get_power_on_volume),
        ):
            try:
                data[key] = float(await read())
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch %s: %s", key, err)

        # The user-defined input names (the media player's sources)
        data["input_names"] = await self.device.async_get_input_names()

        data.update(await self._async_static_info())
        return data

    async def _async_static_info(self) -> dict[str, Any]:
        """Firmware version and MAC address. Read until they have been read once, then remembered."""
        if "firmware_version" not in self._static:
            try:
                version_resp = await self.device.async_get_version()
                self._static["firmware_version"] = version_resp.get("version", "1.2.0")
                self._static["git_commit"] = version_resp.get("gitCommit", "")
                self._static["build_time"] = version_resp.get("buildTime", "")
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch version: %s", err)

        if "mac_address" not in self._static:
            try:
                self._static["mac_address"] = await self.device.async_get_macaddress()
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.warning("Could not fetch MAC address (Error: %s - %s)", type(err).__name__, err)
                return {**self._static, "mac_address": "00:00:00:00:00:00"}  # not remembered: try again next time

        return dict(self._static)
