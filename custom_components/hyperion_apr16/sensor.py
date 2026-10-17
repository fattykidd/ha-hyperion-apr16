"""Sensor entities for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    """Set up Hyperion sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors = [
        HyperionSensor(coordinator, entry, "audio_format", "Audio Format", None),
        HyperionSensor(coordinator, entry, "video_detail", "Video Signal", None),
        HyperionSensor(coordinator, entry, "volume", "Volume", "dB"),
        HyperionSensor(coordinator, entry, "mute", "Mute State", None),
        HyperionSensor(coordinator, entry, "brightness", "Display Brightness", "%"),
        HyperionSensor(coordinator, entry, "host_ip", "Host IP", None),
        HyperionSensor(coordinator, entry, "bass", "Input Bass", "dB"),
        HyperionSensor(coordinator, entry, "treble", "Input Treble", "dB"),
    ]

    async_add_entities(sensors)


class HyperionSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hyperion APR-16 sensor."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        name_suffix: str,
        unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name_suffix}"
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get(self._key)