"""The AudioControl Hyperion APR-16 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config import APR16Config
from .const import CONF_SESSION_COOKIE, DOMAIN
from .coordinator import HyperionDataUpdateCoordinator
from .device import Apr16

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AudioControl Hyperion APR-16 from a config entry."""
    host = entry.data.get("address", entry.data.get("host"))
    port = entry.data.get("port", 8080)
    name = entry.data.get("name", "AudioControl Hyperion APR-16")
    session_cookie = entry.data.get(CONF_SESSION_COOKIE)

    device_config = APR16Config(
        identifier=entry.entry_id,
        name=name,
        address=host,
        port=port,
    )

    session = async_get_clientsession(hass)
    
    # Initialize the device client, passing the session_cookie for port 80 Atlas endpoints
    device = Apr16(device_config=device_config, session=session, session_cookie=session_cookie)

    coordinator = HyperionDataUpdateCoordinator(hass, device=device)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok