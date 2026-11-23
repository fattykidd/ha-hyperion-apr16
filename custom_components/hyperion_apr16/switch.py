"""Switch entities for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HyperionDataUpdateCoordinator
from .meter_entity import HyperionMeterEntity
from .meters import LevelMeters

_LOG = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hyperion switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device = data["device"]

    switches = [
        HyperionPowerSwitch(coordinator, device, entry),
        HyperionMuteSwitch(coordinator, device, entry),
        HyperionDisplayPowerSwitch(coordinator, device, entry),
        HyperionTriggerSwitch(coordinator, device, entry),
        HyperionDiracSwitch(coordinator, device, entry),
        HyperionLoudnessSwitch(coordinator, device, entry),
        HyperionLevelMetersSwitch(data["meters"], entry),
    ]

    async_add_entities(switches)


class HyperionBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Hyperion switches ensuring proper device grouping."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the switch."""
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


class HyperionPowerSwitch(HyperionBaseSwitch):
    """Switch to toggle device main power state."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "power_switch", "Power")

    @property
    def is_on(self) -> bool:
        """Return True if processor is powered on."""
        return bool(self.coordinator.data.get("power", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the processor on."""
        await self._device.power_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the processor off."""
        await self._device.power_off()
        await self.coordinator.async_request_refresh()


class HyperionMuteSwitch(HyperionBaseSwitch):
    """Switch to toggle audio mute state."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "mute_switch", "Mute")

    @property
    def is_on(self) -> bool:
        """Return True if system is muted."""
        return bool(self.coordinator.data.get("mute", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the audio."""
        await self._device.set_mute(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the audio."""
        await self._device.set_mute(False)
        await self.coordinator.async_request_refresh()


class HyperionDisplayPowerSwitch(HyperionBaseSwitch):
    """Switch to toggle front panel display on or off."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "display_power", "Display Power")

    @property
    def is_on(self) -> bool:
        """Return True if display brightness is above 0."""
        return self.coordinator.data.get("brightness", 0) > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn front display on (set to 50% brightness)."""
        await self._device.set_display_brightness(50)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn front display off (set brightness to 0%)."""
        await self._device.set_display_brightness(0)
        await self.coordinator.async_request_refresh()


class HyperionTriggerSwitch(HyperionBaseSwitch):
    """Switch to toggle 12V output trigger state."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "trigger_out", "12V Trigger")

    @property
    def is_on(self) -> bool:
        """Return True if 12V trigger output is active."""
        return bool(self.coordinator.data.get("trigger_state", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable 12V trigger output."""
        await self._device.set_trigger(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable 12V trigger output."""
        await self._device.set_trigger(False)
        await self.coordinator.async_request_refresh()


class HyperionDiracSwitch(HyperionBaseSwitch):
    """Switch to turn Dirac filtering on or off."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "dirac_switch", "Dirac Active")

    @property
    def is_on(self) -> bool | None:
        """Return True if Dirac filtering is on, or None until the processor has reported it."""
        return (self.coordinator.data or {}).get("dirac_active")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn Dirac filtering on."""
        await self._set_filtering(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Dirac filtering off."""
        await self._set_filtering(False)

    async def _set_filtering(self, enabled: bool) -> None:
        await self._device.async_set_dirac_filtering(enabled)
        if self.coordinator.data:
            self.coordinator.async_set_updated_data({**self.coordinator.data, "dirac_active": enabled})
        await self.coordinator.async_request_refresh()


class HyperionLoudnessSwitch(HyperionBaseSwitch):
    """Switch for loudness compensation, which adds bass at low listening levels."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "loudness_switch", "Loudness")

    @property
    def available(self) -> bool:
        """Unavailable while the processor is unreachable, or on firmware without loudness."""
        supported = (self.coordinator.data or {}).get("loudness_supported")
        return super().available and supported is not False

    @property
    def is_on(self) -> bool | None:
        """Return True if loudness is on, or None until the processor has reported it."""
        return (self.coordinator.data or {}).get("loudness")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn loudness on."""
        await self._set_loudness(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn loudness off."""
        await self._set_loudness(False)

    async def _set_loudness(self, enabled: bool) -> None:
        await self._device.async_set_loudness(enabled)
        self.coordinator.async_apply_pushed({"loudness": enabled})  # the speakers stream confirms it


class HyperionLevelMetersSwitch(HyperionMeterEntity, SwitchEntity):
    """Starts and stops the level meters. They switch themselves off after a while."""

    _attr_icon = "mdi:chart-bar"

    def __init__(self, meters: LevelMeters, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(meters, entry, "level_meters", "Level Meters")

    @property
    def is_on(self) -> bool:
        """Return True while the level meters are running."""
        return self._meters.active

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the level meters."""
        self._meters.start()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the level meters."""
        await self._meters.stop()
