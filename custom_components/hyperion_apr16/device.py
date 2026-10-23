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
        """Fetch current status/state dictionary from the device via REST API endpoints."""
        session = await self._get_session()

        async def fetch_endpoint(endpoint: str) -> Any:
            """Helper to safely fetch a single resource endpoint."""
            try:
                async with session.get(f"{self._base_url}{endpoint}", timeout=2) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                pass
            return None

        # Fetch all resource states concurrently with your exact API paths
        power_res, vol_res, mute_res, input_res, mode_res, bright_res, temp_res = await asyncio.gather(
            fetch_endpoint("/v1/power"),
            fetch_endpoint("/v1/vol"),
            fetch_endpoint("/v1/mute"),
            fetch_endpoint("/v1/input"),
            fetch_endpoint("/v1/audiomode"),  # Updated route path
            fetch_endpoint("/v1/displaybrightness"),
            fetch_endpoint("/v1/temperature"),
        )

        # 1. Parse Power
        power = False
        if isinstance(power_res, dict):
            val = power_res.get("state", power_res.get("value", power_res.get("status", False)))
            power = str(val) in ("1", "true", "True", "ON", "on")

        # 2. Parse Volume
        volume = 0.0
        if isinstance(vol_res, dict):
            try:
                val = vol_res.get("level", vol_res.get("state", vol_res.get("value", 0.0)))
                volume = float(val)
            except (ValueError, TypeError):
                pass

        # 3. Parse Mute
        mute = False
        if isinstance(mute_res, dict):
            val = mute_res.get("state", mute_res.get("level", mute_res.get("value", False)))
            mute = str(val) in ("1", "true", "True", "ON", "on", "yes", "YES")

        # 4. Parse Active Input
        active_input = "Unknown"
        if isinstance(input_res, dict):
            active_input = str(input_res.get("name", input_res.get("state", input_res.get("value", "Unknown"))))

        # 5. Parse Audio Mode (e.g., {"mode":"native"})
        audio_mode = "Auto"
        if isinstance(mode_res, dict):
            audio_mode = str(mode_res.get("mode", mode_res.get("state", mode_res.get("value", "Auto"))))

        # 6. Parse Brightness
        brightness = 80
        if isinstance(bright_res, dict):
            try:
                val = bright_res.get("brightness", bright_res.get("level", bright_res.get("state", 80)))
                brightness = int(val)
            except (ValueError, TypeError):
                pass

        # 7. Parse Temperature
        temperature = 0.0
        if isinstance(temp_res, dict):
            try:
                val = temp_res.get("temperature", temp_res.get("state", 0.0))
                temperature = float(val)
            except (ValueError, TypeError):
                pass

        return {
            "power": power,
            "volume": volume,
            "mute": mute,
            "active_input": active_input,
            "audio_mode": audio_mode,
            "brightness": brightness,
            "temperature": temperature,
        }