"""Async client for AudioControl Hyperion APR-16."""

from __future__ import annotations

import asyncio
import logging

from .config import APR16Config

_LOGGER = logging.getLogger(__name__)


class Apr16:
    """Async communication client for the AudioControl Hyperion APR-16 processor."""

    def __init__(
        self, device_config: APR16Config, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize the device client."""
        self._config = device_config
        self._loop = loop
        self._writer: asyncio.StreamWriter | None = None
        self._reader: asyncio.StreamReader | None = None

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._config.name

    @property
    def host(self) -> str:
        """Return the device host/ip address."""
        return self._config.address

    @property
    def port(self) -> int:
        """Return the device port."""
        return self._config.port

    async def async_connect(self) -> bool:
        """Establish connection to the processor."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._config.address, self._config.port
            )
            _LOGGER.info(
                "Connected to AudioControl Hyperion APR-16 at %s:%s",
                self._config.address,
                self._config.port,
            )
            return True
        except (TimeoutError, OSError) as err:
            _LOGGER.error("Failed to connect to Hyperion APR-16: %s", err)
            return False

    async def async_disconnect(self) -> None:
        """Disconnect from the processor."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.drain()
            except (TimeoutError, OSError) as err:
                _LOGGER.debug("Error closing connection during disconnect: %s", err)
            self._writer = None
            self._reader = None

    async def async_power_on(self) -> None:
        """Turn the processor power on."""
        await self.async_send_command("POWER ON")

    async def power_on(self) -> None:
        """Turn the processor power on (alias)."""
        await self.async_power_on()

    async def async_power_off(self) -> None:
        """Turn the processor power off."""
        await self.async_send_command("POWER OFF")

    async def power_off(self) -> None:
        """Turn the processor power off (alias)."""
        await self.async_power_off()

    async def async_send_command(self, command: str) -> None:
        """Send a command string to the processor."""
        if not self._writer:
            connected = await self.async_connect()
            if not connected:
                return

        try:
            self._writer.write(f"{command}\r\n".encode())
            await self._writer.drain()
        except (TimeoutError, OSError) as err:
            _LOGGER.error("Error sending command '%s' to Hyperion: %s", command, err)
            await self.async_disconnect()

    async def async_get_status(self) -> dict:
        """Fetch current status/state dictionary from the device."""
        # TODO: Implement actual parsing of device response strings or queries here
        return {
            "power": True,
            "volume": -20.0,
            "mute": False,
            "active_input": "HDMI 1",
            "audio_mode": "Auto",
            "brightness": 80,
        }
