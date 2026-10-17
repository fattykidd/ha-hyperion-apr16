"""Data update coordinator for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from device import Apr16

_LOG = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=5)


class HyperionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching AudioControl Hyperion data from the device."""

    def __init__(self, hass: HomeAssistant, device: Apr16) -> None:
        """Initialize coordinator."""
        self.device = device
        super().__init__(
            hass,
            _LOG,
            name="Hyperion APR-16",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the APR-16 processor."""
        try:
            # Verify/refresh connection and update internal attributes
            await self.device.verify_connection()

            # Gather additional telemetry states in a single dictionary for entities
            power_state = self.device.state
            volume = await self.device.get_volume()
            mute = await self.device.get_mute()
            active_input = await self.device.get_active_input()
            brightness = await self.device.get_display_brightness()
            host_ip = await self.device.get_host_ip()
            
            # Fetch optional details safely
            try:
                audio_format = await self.device.get_audio_format()
            except Exception:
                audio_format = "Unknown"

            try:
                video_detail = await self.device.get_video_detail()
            except Exception:
                video_detail = {}

            try:
                audio_detail = await self.device.get_audio_detail()
            except Exception:
                audio_detail = {}

            try:
                bass = await self.device.get_input_bass(active_input or "HDMI 1")
            except Exception:
                bass = 0

            try:
                treble = await self.device.get_input_treble(active_input or "HDMI 1")
            except Exception:
                treble = 0

            return {
                "power": power_state,
                "volume": volume,
                "mute": mute,
                "active_input": active_input,
                "brightness": brightness,
                "host_ip": host_ip,
                "audio_format": audio_format,
                "video_detail": video_detail,
                "audio_detail": audio_detail,
                "bass": bass,
                "treble": treble,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Hyperion APR-16: {err}") from err