"""Base class for the entities that show or control the level meters."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .meters import LevelMeters


class HyperionMeterEntity(Entity):
    """An entity that follows LevelMeters instead of the coordinator, so meter readings never refresh it."""

    _attr_should_poll = False

    def __init__(self, meters: LevelMeters, entry: ConfigEntry, key: str, name_suffix: str) -> None:
        """Initialize the entity."""
        self._meters = meters
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    async def async_added_to_hass(self) -> None:
        """Start following the meters."""
        self.async_on_remove(self._meters.add_listener(self.async_write_ha_state))
