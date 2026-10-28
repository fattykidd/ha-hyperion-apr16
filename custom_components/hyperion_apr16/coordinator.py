"""Data update coordinator for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helper import percent_to_db  # <--- 1. Import your volume helper

_LOG = logging.getLogger(__name__)


class HyperionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Hyperion data central polling."""

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOG,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.device = device

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Hyperion APR-16 processor."""
        try:
            # Fetch base status dict directly from Apr16 client in device.py
            data = await self.device.async_get_status()

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

            try:
                version_resp = await self.device.async_get_version()
                data["firmware_version"] = version_resp.get("version", "1.2.0")
                data["git_commit"] = version_resp.get("gitCommit", "")
                data["build_time"] = version_resp.get("buildTime", "")
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch version: %s", err)

            try:
                mac_resp = await self.device.async_get_macaddress()
                data["mac_address"] = mac_resp
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch MAC address: %s", err)
                
            return data
        except (ClientError, TimeoutError, OSError, Exception) as err:
            raise UpdateFailed(
                f"Error communicating with Hyperion APR-16: {err}"
            ) from err