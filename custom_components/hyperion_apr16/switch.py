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
            "identifiers": {(DOMAIN, coordinator.device.host)},
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
