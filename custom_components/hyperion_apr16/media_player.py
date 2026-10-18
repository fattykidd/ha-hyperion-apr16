"""Media player entity for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    """Set up the Hyperion media player from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: HyperionDataUpdateCoordinator = data["coordinator"]
    device = data["device"]

    async_add_entities([HyperionMediaPlayer(coordinator, device, entry)])


class HyperionMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of an AudioControl Hyperion APR-16 Media Player."""

    def __init__(
        self,
        coordinator: HyperionDataUpdateCoordinator,
        device: Any,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_name = entry.title
        self._attr_device_class = "receiver"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if not self.coordinator.data or not self.coordinator.data.get("power", False):
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 to 1.0 mapped from dB or raw)."""
        vol = self.coordinator.data.get("volume", 0.0)
        # Home Assistant expects volume level as a float between 0.0 and 1.0.
        # Assuming volume from device is in dB (e.g., -80.0 to 0.0) or percentage.
        # Adjust conversion based on your device.py implementation.
        try:
            # Simple normalization example if volume is stored as dB
            return max(0.0, min(1.0, (float(vol) + 80.0) / 80.0))
        except (ValueError, TypeError):
            return 0.0

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self.coordinator.data.get("mute", False)

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.coordinator.data.get("active_input")

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        # You can map your physical inputs here or pull them from device capabilities
        return ["HDMI 1", "HDMI 2", "HDMI 3", "HDMI 4", "Optical", "Coaxial", "Analog"]

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._device.power_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._device.power_off()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0.0 to 1.0."""
        # Convert 0.0-1.0 float back to your device's volume scale
        db_val = -80.0 + (volume * 80.0)
        await self._device.set_volume(db_val)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media."""
        await self._device.set_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.set_active_input(source)
        await self.coordinator.async_request_refresh()
