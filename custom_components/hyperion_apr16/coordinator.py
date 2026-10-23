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
        try:
            # Fetch base status dict directly from Apr16 client in device.py
            data = await self.device.async_get_status()

            # Attach device property metadata
            data["host_ip"] = getattr(self.device, "host", None)

            return data
        except (ClientError, TimeoutError, OSError, Exception) as err:
            raise UpdateFailed(
                f"Error communicating with Hyperion APR-16: {err}"
            ) from err
