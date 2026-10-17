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

AUDIO_MODES = ["Auto", "Stereo", "Dolby Surround", "DTS Neural:X", "Direct", "Pure Audio"]


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
        self._attr_options = AUDIO_MODES

    @property
    def current_option(self) -> str | None:
        """Return the selected audio mode option."""
        # You can tie this to a coordinator key if your device client exposes it
        return self.coordinator.data.get("audio_mode", "Auto")

    async def async_select_option(self, option: str) -> None:
        """Change the selected audio mode."""
        try:
            await self._device.set_audio_mode(option)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to set audio mode to %s: %s", option, err)