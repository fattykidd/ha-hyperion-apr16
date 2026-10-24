"""Button entities for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from homeassistant.components.button import ButtonEntity
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
    """Set up Hyperion buttons from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device = data["device"]

    buttons = [
        HyperionRebootButton(coordinator, device, entry),
        HyperionHpdButton(coordinator, device, entry),
        HyperionBassUpButton(coordinator, device, entry),
        HyperionBassDownButton(coordinator, device, entry),
        HyperionTrebleUpButton(coordinator, device, entry),
        HyperionTrebleDownButton(coordinator, device, entry),
        HyperionBrightnessUpButton(coordinator, device, entry),
        HyperionBrightnessDownButton(coordinator, device, entry),
        HyperionVolumeButton(coordinator, device, entry, "up"),
        HyperionVolumeButton(coordinator, device, entry, "down"),
    ]

    async_add_entities(buttons)


class HyperionBaseButton(CoordinatorEntity, ButtonEntity):
    """Base button entity for Hyperion."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
        key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = f"{entry.title} {name_suffix}"

        host = getattr(coordinator.device, "host", None)
        if not isinstance(host, str) or not host:
            host = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }


class HyperionRebootButton(HyperionBaseButton):
    """Button to reboot the processor."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "reboot", "Reboot")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self._device.reboot()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to reboot Hyperion APR-16: %s", err)


class HyperionHpdButton(HyperionBaseButton):
    """Button to trigger Hot Plug Detect (HPD)."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "hpd", "Trigger HPD")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self._device.trigger_hpd()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to trigger HPD on Hyperion APR-16: %s", err)


class HyperionBassUpButton(HyperionBaseButton):
    """Button to increase input bass by 1dB."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "bass_up", "Bass +1dB")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            active_input = self.coordinator.data.get("active_input", "HDMI 1")
            current = await self._device.get_input_bass(active_input)
            await self._device.set_input_bass(active_input, current + 1.0)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to increase bass: %s", err)


class HyperionBassDownButton(HyperionBaseButton):
    """Button to decrease input bass by 1dB."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "bass_down", "Bass -1dB")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            active_input = self.coordinator.data.get("active_input", "HDMI 1")
            current = await self._device.get_input_bass(active_input)
            await self._device.set_input_bass(active_input, current - 1.0)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to decrease bass: %s", err)


class HyperionTrebleUpButton(HyperionBaseButton):
    """Button to increase input treble by 1dB."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "treble_up", "Treble +1dB")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            active_input = self.coordinator.data.get("active_input", "HDMI 1")
            current = await self._device.get_input_treble(active_input)
            await self._device.set_input_treble(active_input, current + 1.0)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to increase treble: %s", err)


class HyperionTrebleDownButton(HyperionBaseButton):
    """Button to decrease input treble by 1dB."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "treble_down", "Treble -1dB")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            active_input = self.coordinator.data.get("active_input", "HDMI 1")
            current = await self._device.get_input_treble(active_input)
            await self._device.set_input_treble(active_input, current - 1.0)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to decrease treble: %s", err)


class HyperionBrightnessUpButton(HyperionBaseButton):
    """Button to increase display brightness by 10%."""

    def __init__(self, coordinator, device, entry):
        super().__init__(coordinator, device, entry, "brightness_up", "Brightness +10%")

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            current = self.coordinator.data.get("brightness", 50)
            new_val = min(100, current + 10)
            await self._device.set_display_brightness(new_val)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to increase brightness: %s", err)


class HyperionBrightnessDownButton(HyperionBaseButton):
    """Button to decrease display brightness by 10%."""

    def __init__(self, coordinator, device, entry):
        super().__init__(
            coordinator, device, entry, "brightness_down", "Brightness -10%"
        )

    async def async_press(self) -> None:
        """Handle the data and button press."""
        try:
            current = self.coordinator.data.get("brightness", 50)
            new_val = max(0, current - 10)
            await self._device.set_display_brightness(new_val)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to decrease brightness: %s", err)

class HyperionVolumeButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Volume Up or Down button."""

    def __init__(self, coordinator, device, entry, direction: str) -> None:
        """Initialize the volume button."""
        super().__init__(coordinator)
        self._device = device
        self._direction = direction  # "up" or "down"
        self._attr_unique_id = f"{entry.entry_id}_volume_{direction}"
        self._attr_name = f"{entry.title} Volume {'Up' if direction == 'up' else 'Down'}"
        self._attr_icon = "mdi:volume-plus" if direction == "up" else "mdi:volume-minus"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    async def async_press(self) -> None:
        """Handle the button press to adjust volume by 1%."""
        try:
            # Get current volume from coordinator data (0-100 scale)
            current_vol = float(self.coordinator.data.get("volume", 0.0))
            
            if self._direction == "up":
                new_vol = min(100.0, current_vol + 1.0)
            else:
                new_vol = max(0.0, current_vol - 1.0)

            await self._device.set_volume(new_vol)
            await self.coordinator.async_request_refresh()
        except (ClientError, OSError) as err:
            _LOG.error("Failed to adjust volume %s: %s", self._direction, err)   
