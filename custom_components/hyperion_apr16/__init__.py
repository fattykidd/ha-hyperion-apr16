"""The AudioControl Hyperion APR-16 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_PORT
from .coordinator import HyperionDataUpdateCoordinator
from device import Apr16
from config import APR16Config

_LOG = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AudioControl Hyperion APR-16 from a config entry."""
    address = entry.data[CONF_ADDRESS]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    name = entry.data.get(CONF_NAME, "Hyperion APR-16")

    # Initialize your existing device communication class
    device_config = APR16Config(
        identifier=entry.entry_id,
        name=name,
        address=address,
        port=port,
    )
    device = Apr16(device_config=device_config, loop=hass.loop)

    # Initialize the coordinator
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