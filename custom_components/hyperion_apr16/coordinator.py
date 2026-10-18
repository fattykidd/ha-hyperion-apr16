"""Data update coordinator for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

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
        data: dict[str, Any] = {}
        try:
            data["power"] = await self.device.get_power()
            data["volume"] = await self.device.get_volume()
            data["mute"] = await self.device.get_mute()
            data["active_input"] = await self.device.get_active_input()
            data["audio_format"] = await self.device.get_audio_format()
            data["audio_mode"] = await self.device.get_audio_mode()
            data["video_detail"] = await self.device.get_video_detail()
            data["brightness"] = await self.device.get_display_brightness()
            data["host_ip"] = getattr(self.device, "host", None)

            # Retrieve active input bass/treble if available
            if data.get("active_input"):
                data["bass"] = await self.device.get_input_bass(data["active_input"])
                data["treble"] = await self.device.get_input_treble(
                    data["active_input"]
                )

            return data
        except (ClientError, TimeoutError, OSError) as err:
            raise UpdateFailed(
                f"Error communicating with Hyperion APR-16: {err}"
            ) from err
