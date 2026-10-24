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
        HyperionToneButton(coordinator, device, entry, "bass", "up"),
        HyperionToneButton(coordinator, device, entry, "bass", "down"),
        HyperionToneButton(coordinator, device, entry, "treble", "up"),
        HyperionToneButton(coordinator, device, entry, "treble", "down"),
        HyperionBrightnessButton(coordinator, device, entry, "up"),
        HyperionBrightnessButton(coordinator, device, entry, "down"),
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


class HyperionToneButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Bass or Treble adjustment button (+ / -)."""

    def __init__(self, coordinator, device, entry, tone_type: str, direction: str) -> None:
        """Initialize the tone button ('bass' or 'treble', 'up' or 'down')."""
        super().__init__(coordinator)
        self._device = device
        self._tone_type = tone_type  # "bass" or "treble"
        self._direction = direction  # "up" or "down"
        
        step = 1.0
        self._step = step if direction == "up" else -step
        
        self._attr_unique_id = f"{entry.entry_id}_{tone_type}_{direction}"
        self._attr_name = f"{entry.title} {tone_type.capitalize()} {'Up' if direction == 'up' else 'Down'}"
        self._attr_icon = "mdi:equalizer"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    async def async_press(self) -> None:
        """Handle the button press to adjust tone optimistically."""
        try:
            # 1. Get current level and active input ID from coordinator data
            current_val = float(self.coordinator.data.get(self._tone_type, 0.0))
            input_id = self.coordinator.data.get("input_id", 1)
            
            # 2. Calculate new level (clamped between -12 and 12 dB)
            new_level = int(round(max(-12.0, min(12.0, current_val + self._step))))

            # 3. Send command to device
            if self._tone_type == "bass":
                await self._device.set_input_bass(input_id, new_level)
            else:
                await self._device.set_input_treble(input_id, new_level)

            # 4. Optimistically update local coordinator data for instant UI response
            if self.coordinator.data:
                self.coordinator.data[self._tone_type] = float(new_level)
                self.coordinator.async_update_listeners()

        except (ClientError, OSError) as err:
            _LOG.error("Failed to adjust %s %s: %s", self._tone_type, self._direction, err)


class HyperionBrightnessButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Panel Brightness Up or Down button."""

    def __init__(self, coordinator, device, entry, direction: str) -> None:
        """Initialize the brightness button."""
        super().__init__(coordinator)
        self._device = device
        self._direction = direction  # "up" or "down"
        self._step = 10  # 10% adjustment per press
        
        self._attr_unique_id = f"{entry.entry_id}_brightness_{direction}"
        self._attr_name = f"{entry.title} Brightness {'Up' if direction == 'up' else 'Down'}"
        self._attr_icon = "mdi:brightness-increase" if direction == "up" else "mdi:brightness-decrease"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "AudioControl",
            "model": "Hyperion APR-16",
        }

    async def async_press(self) -> None:
        """Handle the button press to adjust panel brightness optimistically."""
        try:
            # Get current brightness from coordinator data (0-100 scale)
            current_brightness = int(self.coordinator.data.get("brightness", 50))
            
            if self._direction == "up":
                new_brightness = min(100, current_brightness + self._step)
            else:
                new_brightness = max(0, current_brightness - self._step)

            # 1. Send command to the device
            await self._device.set_brightness(new_brightness)

            # 2. Optimistically update local coordinator data so slider & UI sync instantly
            if self.coordinator.data:
                self.coordinator.data["brightness"] = new_brightness
                self.coordinator.async_update_listeners()

        except (ClientError, OSError) as err:
            _LOG.error("Failed to adjust brightness %s: %s", self._direction, err)

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

            # 1. Send the command to the device immediately
            await self._device.set_volume(new_vol)

            # 2. Optimistically update local coordinator data so UI responds instantly
            if self.coordinator.data:
                self.coordinator.data["volume"] = new_vol
                self.coordinator.async_update_listeners()

        except (ClientError, OSError) as err:
            _LOG.error("Failed to adjust volume %s: %s", self._direction, err)