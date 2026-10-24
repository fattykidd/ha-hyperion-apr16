"""Number entity for AudioControl Hyperion APR-16 panel brightness."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HyperionDataUpdateCoordinator

_LOG = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hyperion brightness number entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device = data["device"]

    async_add_entities([HyperionBrightnessNumber(coordinator, device, entry)])


class HyperionBrightnessNumber(CoordinatorEntity, NumberEntity):
    """Representation of the Panel Brightness slider."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the brightness number entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_panel_brightness"
        self._attr_name = f"{entry.title} Panel Brightness"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:brightness-6"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current brightness value."""
        data = self.coordinator.data or {}
        return float(data.get("brightness", 100))

    async def async_set_native_value(self, value: float) -> None:
        """Set new brightness value."""
        try:
            await self._device.set_brightness(value)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to set panel brightness: %s", err)