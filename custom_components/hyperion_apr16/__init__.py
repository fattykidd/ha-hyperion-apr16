"""The AudioControl Hyperion APR-16 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config import APR16Config
from .const import DOMAIN
from .coordinator import HyperionDataUpdateCoordinator
from .device import Apr16  # Import Apr16 directly

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AudioControl Hyperion APR-16 from a config entry."""
    # Support both "address" (used in tests) and "host" (used in config flow)
    host = entry.data.get("address", entry.data.get("host"))
    port = entry.data.get("port", 8080)
    name = entry.data.get("name", "AudioControl Hyperion APR-16")

    device_config = APR16Config(
        identifier=entry.entry_id,  # Provide the required unique identifier
        name=name,
        address=host,
        port=port,
    )

    device = Apr16(device_config=device_config)

    # Initialize the coordinator...
    coordinator = HyperionDataUpdateCoordinator(hass, device)

    # Perform initial refresh to make sure device is online
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "coordinator": coordinator,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
