"""Sensor entities for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
        HyperionPowerSensor(coordinator, entry),
        HyperionAbsoluteVolumeSensor(coordinator, entry),
        HyperionRelativeVolumeSensor(coordinator, entry),
        HyperionMuteSensor(coordinator, entry),
        HyperionSensor(coordinator, entry, "audio_format", "Audio Format", None),
        HyperionSensor(coordinator, entry, "video_detail", "Video Signal", None),
        HyperionSensor(coordinator, entry, "brightness", "Display Brightness", "%"),
        HyperionSensor(coordinator, entry, "temperature", "Temperature", "°C", SensorDeviceClass.TEMPERATURE),
        HyperionSensor(coordinator, entry, "host_ip", "Host IP", None),
        HyperionSensor(coordinator, entry, "bass", "Input Bass", "dB"),
        HyperionSensor(coordinator, entry, "treble", "Input Treble", "dB"),
    ]

    async_add_entities(sensors)


class HyperionBaseSensor(CoordinatorEntity[HyperionDataUpdateCoordinator], SensorEntity):
    """Base representation of a Hyperion APR-16 sensor."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        host = getattr(coordinator.device, "host", None)
        if not isinstance(host, str) or not host:
            host = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }


class HyperionPowerSensor(HyperionBaseSensor):
    """Representation of the Hyperion Power State."""

    _attr_name = "Power State"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: HyperionDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize power sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power_state"
        self._attr_name = f"{entry.title} Power State"

    @property
    def native_value(self) -> str:
        """Return the state of the power sensor."""
        data = self.coordinator.data
        if not data:
            return "Off"
        power = data.get("power", False)
        return "On" if power else "Off"


class HyperionAbsoluteVolumeSensor(HyperionBaseSensor):
    """Representation of Hyperion Absolute Volume (Percentage)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator: HyperionDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize absolute volume sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_volume_absolute"
        self._attr_name = f"{entry.title} Absolute Volume"

    @property
    def native_value(self) -> float | None:
        """Return the absolute volume percentage."""
        data = self.coordinator.data
        if not data:
            return None
        val = data.get("volume")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return None


class HyperionRelativeVolumeSensor(HyperionBaseSensor):
    """Representation of Hyperion Relative Volume (dB)."""

    _attr_native_unit_of_measurement = "dB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:volume-medium"

    def __init__(self, coordinator: HyperionDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize relative volume sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_volume_relative"
        self._attr_name = f"{entry.title} Relative Volume"

    @property
    def native_value(self) -> float | None:
        """Return the relative volume in dB."""
        data = self.coordinator.data
        if not data:
            return None
        val = data.get("volume_db")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return None

class HyperionMuteSensor(HyperionBaseSensor):
    """Representation of Hyperion Mute State."""

    _attr_icon = "mdi:volume-mute"

    def __init__(self, coordinator: HyperionDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize mute sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mute"
        self._attr_name = f"{entry.title} Mute State"

    @property
    def native_value(self) -> str:
        """Return the friendly mute state."""
        data = self.coordinator.data
        if not data:
            return "Off"
        muted = data.get("mute", False)
        return "Muted" if muted else "Off"

class HyperionSensor(HyperionBaseSensor):
    """Representation of a standard Hyperion APR-16 sensor."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        name_suffix: str,
        unit: str | None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        """Initialize standard sensor."""
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name_suffix}"
        if unit:
            self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get(self._key)
