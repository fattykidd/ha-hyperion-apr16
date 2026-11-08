"""Select entities for AudioControl Hyperion APR-16 audio modes and Dirac slots."""

from __future__ import annotations

import logging
import re
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
#_LOGGER = logging.getLogger(__name__)

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

API_TO_UI_MAPPING = {v: k for k, v in AUDIO_MODE_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hyperion select entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device = data["device"]

    # Pull the exact slot list from coordinator data, with a safe fallback
    (
        coordinator.data.get("dirac_filter_slots")
        if coordinator.data
        else None
    ) or ["Slot 0", "Slot 1", "Slot 2"]

    async_add_entities([
        HyperionAudioModeSelect(coordinator, device, entry),
        HyperionDiracSlotSelect(coordinator, device, entry),
    ])


class HyperionBaseSelect(CoordinatorEntity, SelectEntity):
    """Base class for Hyperion select entities ensuring proper device grouping."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }


class HyperionAudioModeSelect(HyperionBaseSelect):
    """Representation of the Audio Mode select entity."""

    def __init__(self, coordinator, device, entry) -> None:
        super().__init__(coordinator, device, entry, "audio_mode", "Audio Mode")
        self._attr_options = list(AUDIO_MODE_MAPPING.keys())

    @property
    def current_option(self) -> str | None:
        """Return the selected audio mode option."""
        raw_mode = self.coordinator.data.get("audio_mode", "native")
        return API_TO_UI_MAPPING.get(raw_mode, "Native")

    async def async_select_option(self, option: str) -> None:
        """Change the selected audio mode."""
        try:
            api_value = AUDIO_MODE_MAPPING.get(option, "native")
            await self._device.set_audio_mode(api_value)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to set audio mode to %s: %s", option, err)


class HyperionDiracSlotSelect(HyperionBaseSelect):
    """Representation of the Dirac Filter Slot select entity."""

    def __init__(self, coordinator, device, entry) -> None:
        super().__init__(coordinator, device, entry, "active_slot", "Dirac Filter Slot")
        self._attr_options = ["Slot 1", "Slot 2", "Slot 3"]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected slot by mapping the active_slot index to options."""
        if not self.coordinator.data:
            return None

        slot_idx = self.coordinator.data.get("active_slot", 0)
        if isinstance(slot_idx, int) and 0 <= slot_idx < len(self._attr_options):
            return self._attr_options[slot_idx]
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and parse slot names by delimiters."""
        if self.coordinator.data and "dirac_slots_raw" in self.coordinator.data:
            raw_text = self.coordinator.data["dirac_slots_raw"]
            
            # Extract everything strictly bounded between \x0b and \x1a
            extracted_slots = re.findall(r'\x0b([^\x1a]+)\x1a', raw_text)
            
            if extracted_slots:
                cleaned = [s.strip() for s in extracted_slots if s.strip()]
                if cleaned:
                    self._attr_options = cleaned
                    
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the active slot index by matching the selected custom name."""
        slots = self.options
        try:
            slot_index = slots.index(option)
        except ValueError:
            slot_index = 0
            
        await self._device.async_set_dirac_filter_slot(slot_index)
        
        # Request an immediate refresh so the coordinator fetches the new live active_slot
        await self.coordinator.async_request_refresh()