"""Async REST client for AudioControl Hyperion APR-16."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .config import APR16Config

_LOGGER = logging.getLogger(__name__)


class Apr16:
    """Async REST client for the AudioControl Hyperion APR-16 processor."""

    def __init__(
        self, device_config: APR16Config, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize the device client."""
        self._config = device_config
        self._loop = loop
        self._base_url = f"http://{device_config.address}:{device_config.port}"
        self._session: aiohttp.ClientSession | None = None

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

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp client session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def async_connect(self) -> bool:
        """Verify connectivity to the processor REST API."""
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/v1/status", timeout=5) as response:
                if response.status == 200:
                    _LOGGER.info(
                        "Connected to AudioControl Hyperion APR-16 REST API at %s",
                        self._base_url,
                    )
                    return True
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.error("Failed to connect to Hyperion APR-16 REST API: %s", err)
        return False

    async def async_disconnect(self) -> None:
        """Clean up HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def async_power_on(self) -> None:
        """Turn the processor power on."""
        await self._send_request("POST", "/v1/power/on")

    async def async_power_off(self) -> None:
        """Turn the processor power off."""
        await self._send_request("POST", "/v1/power/off")

    async def _send_request(
        self, method: str, endpoint: str, json_data: dict | None = None
    ) -> Any:
        """Send an HTTP request to the processor."""
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"
        try:
            async with session.request(
                method, url, json=json_data, timeout=5
            ) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Error executing %s on %s: %s", method, url, err)
            raise

    async def async_get_status(self) -> dict:
        """Fetch current status/state dictionary from the device via REST API endpoints."""
        session = await self._get_session()

        async def fetch_endpoint(endpoint: str) -> Any:
            """Helper to safely fetch a single resource endpoint."""
            try:
                async with session.get(
                    f"{self._base_url}{endpoint}", timeout=2
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.debug("Endpoint %s unavailable or failed: %s", endpoint, err)
            return None

        # Fetch all resource states concurrently with your exact API paths
        (
            power_res,
            vol_res,
            mute_res,
            input_res,
            mode_res,
            bright_res,
            temp_res,
        ) = await asyncio.gather(
            fetch_endpoint("/v1/power"),
            fetch_endpoint("/v1/vol"),
            fetch_endpoint("/v1/mute"),
            fetch_endpoint("/v1/input"),
            fetch_endpoint("/v1/audiomode"),
            fetch_endpoint("/v1/displaybrightness"),
            fetch_endpoint("/v1/temperature"),
        )

        # 1. Parse Power
        power = False
        if isinstance(power_res, dict):
            val = power_res.get(
                "state", power_res.get("value", power_res.get("status", False))
            )
            power = str(val) in ("1", "true", "True", "ON", "on")

        # 2. Parse Volume
        volume = 0.0
        if isinstance(vol_res, dict):
            try:
                val = vol_res.get(
                    "level", vol_res.get("state", vol_res.get("value", 0.0))
                )
                volume = float(val)
            except (ValueError, TypeError):
                pass

        # 3. Parse Mute
        mute = False
        if isinstance(mute_res, dict):
            val = mute_res.get(
                "state", mute_res.get("level", mute_res.get("value", False))
            )
            mute = str(val) in ("1", "true", "True", "ON", "on", "yes", "YES")

        # 4. Parse Active Input
        active_input = "Unknown"
        if isinstance(input_res, dict):
            active_input = str(
                input_res.get(
                    "name", input_res.get("state", input_res.get("value", "Unknown"))
                )
            )

        # 5. Parse Audio Mode
        audio_mode = "Auto"
        if isinstance(mode_res, dict):
            audio_mode = str(
                mode_res.get(
                    "mode", mode_res.get("state", mode_res.get("value", "Auto"))
                )
            )

        # 6. Parse Brightness
        brightness = 80
        if isinstance(bright_res, dict):
            try:
                val = bright_res.get(
                    "brightness",
                    bright_res.get("level", bright_res.get("state", 80)),
                )
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