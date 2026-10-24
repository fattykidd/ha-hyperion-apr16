"""Select entity for AudioControl Hyperion APR-16 audio modes."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HyperionDataUpdateCoordinator

_LOG = logging.getLogger(__name__)

# Map clean UI display names to the exact backend API strings
AUDIO_MODE_MAPPING = {
    "Direct Mode": "dspdirectmode",
    "DTS Neural:X": "dts-nx",
    "Stereo": "2ch",
    "All Channel Stereo": "multich",
    "Dolby Mode": "dolby mode",
    "Native": "native",
    "Dolby Surround": "dolby surround",
}

# Reverse mapping to display friendly names from the raw API state
API_TO_UI_MAPPING = {v: k for k, v in AUDIO_MODE_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hyperion select entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device = data["device"]

    async_add_entities([HyperionAudioModeSelect(coordinator, device, entry)])


class HyperionAudioModeSelect(CoordinatorEntity, SelectEntity):
    """Representation of the Audio Mode select entity."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_audio_mode"
        self._attr_name = f"{entry.title} Audio Mode"
        self._attr_options = list(AUDIO_MODE_MAPPING.keys())
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    @property
    def current_option(self) -> str | None:
        """Return the selected audio mode option."""
        raw_mode = self.coordinator.data.get("audio_mode", "native")
        return API_TO_UI_MAPPING.get(raw_mode, "Native")

    async def async_select_option(self, option: str) -> None:
        """Change the selected audio mode."""
        try:
            # Look up the clean UI name and send the corresponding backend string
            api_value = AUDIO_MODE_MAPPING.get(option, "native")
            await self._device.set_audio_mode(api_value)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to set audio mode to %s: %s", option, err)