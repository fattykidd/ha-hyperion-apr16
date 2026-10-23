"""API client for AudioControl Hyperion APR-16 processor."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .config import APR16Config

_LOG = logging.getLogger(__name__)


class Apr16:
    """Async REST API client for AudioControl Hyperion APR-16."""

    def __init__(
        self,
        host: str | None = None,
        port: int = 8080,
        session: ClientSession | None = None,
        device_config: APR16Config | None = None,
    ) -> None:
        """Initialize the client supporting both direct args and config dataclass."""
        if device_config is not None:
            self.host = device_config.address
            self.port = device_config.port
        else:
            self.host = host or "localhost"
            self.port = port

        self._session = session
        self._base_url = f"http://{self.host}:{self.port}"

    async def _send_request(self, method: str, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """Send an HTTP request to the APR-16 API."""
        if self._session is None:
            self._session = ClientSession()

        url = f"{self._base_url}{endpoint}"
        try:
            async with self._session.request(method, url, json=data, timeout=10) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except (ClientError, TimeoutError, OSError) as err:
            _LOG.error("API request failed for %s: %s", url, err)
            raise

    async def async_connect(self) -> bool:
        """Test connection and verify reachability of the APR-16 processor."""
        try:
            res = await self._send_request("GET", "/v1/version")
            return res is not None
        except Exception as err:
            _LOG.error("Failed to connect to Hyperion APR-16 at %s: %s", self._base_url, err)
            raise

    async def async_get_status(self) -> dict[str, Any]:
        """Fetch comprehensive system status."""
        power_res = await self._send_request("GET", "/v1/power")
        vol_res = await self._send_request("GET", "/v1/vol")
        mute_res = await self._send_request("GET", "/v1/mute")
        input_res = await self._send_request("GET", "/api/atlas/input/active")
        audio_mode_res = await self._send_request("GET", "/v1/audiomode")
        brightness_res = await self._send_request("GET", "/v1/displaybrightness")
        trigger_res = await self._send_request("GET", "/v1/trigger/output")
        audio_format_res = await self._send_request("GET", "/v1/audioformat")
        video_detail_res = await self._send_request("GET", "/v1/videodetail")
        
        temperature = None
        try:
            temp_res = await self._send_request("GET", "/v1/temperature")
            if isinstance(temp_res, dict):
                temperature = float(temp_res.get("temperature", temp_res.get("level", 0.0)))
            elif isinstance(temp_res, (int, float)):
                temperature = float(temp_res)
        except (ValueError, TypeError):
            _LOG.warning("Failed to parse temperature value: %s", temp_res)

        audio_detail = "Unknown"
        try:
            audio_detail_res = await self._send_request("GET", "/v1/audiodetail")
            if isinstance(audio_detail_res, dict):
                audio_detail = audio_detail_res.get("detail", audio_detail_res.get("format", "Unknown"))
            elif isinstance(audio_detail_res, str):
                audio_detail = audio_detail_res
        except (ValueError, TypeError):
            _LOG.warning("Failed to parse audio detail value: %s", audio_detail_res)

        # Parse responses safely
        power = False
        if isinstance(power_res, dict):
            power = str(power_res.get("state", "")).lower() == "on"

        volume = 0.0
        if isinstance(vol_res, dict):
            volume = float(vol_res.get("level", 0.0))

        mute = False
        if isinstance(mute_res, dict):
            mute = bool(mute_res.get("state", mute_res.get("mute", False)))

        active_input = "HDMI 1"
        if isinstance(input_res, dict):
            active_input = input_res.get("name", "HDMI 1")

        audio_mode = "Auto"
        if isinstance(audio_mode_res, dict):
            audio_mode = audio_mode_res.get("mode", "Auto")

        brightness = 50
        if isinstance(brightness_res, dict):
            brightness = int(
                brightness_res.get(
                    "brightness",
                    brightness_res.get("level", brightness_res.get("value", 50)),
                )
            )

        trigger_state = False
        if isinstance(trigger_res, dict):
            val = trigger_res.get("state", trigger_res.get("value", trigger_res.get("level", False)))
            trigger_state = str(val).lower() in ("1", "true", "on")

        audio_format = "PCM"
        if isinstance(audio_format_res, dict):
            audio_format = audio_format_res.get("format", audio_format_res.get("codec", "PCM"))
        elif isinstance(audio_format_res, str):
            audio_format = audio_format_res

        video_detail = "Unknown"
        if isinstance(video_detail_res, dict):
            video_detail = video_detail_res.get(
                "detail", video_detail_res.get("resolution", "Unknown")
            )
        elif isinstance(video_detail_res, str):
            video_detail = video_detail_res

        return {
            "power": power,
            "volume": volume,
            "mute": mute,
            "active_input": active_input,
            "audio_mode": audio_mode,
            "brightness": brightness,
            "trigger_state": trigger_state,
            "audio_format": audio_format,
            "audio_detail": audio_detail,
            "video_detail": video_detail,
            "temperature": temperature,
        }

    async def power_on(self) -> None:
        """Turn the processor power on."""
        await self._send_request("POST", "/v1/power", {"state": "on"})

    async def power_off(self) -> None:
        """Turn the processor power off."""
        await self._send_request("POST", "/v1/power", {"state": "off"})

    async def set_volume(self, level: float) -> None:
        """Set volume level (0-100)."""
        await self._send_request("POST", "/v1/vol", {"level": level})

    async def set_mute(self, mute: bool) -> None:
        """Set mute state."""
        await self._send_request("POST", "/v1/mute", {"state": mute})

    async def set_active_input(self, source: str) -> None:
        """Set active input source."""
        await self._send_request("POST", "/api/atlas/input/active", {"name": source})

    async def set_audio_mode(self, mode: str) -> None:
        """Set the audio processing mode."""
        await self._send_request("POST", "/v1/audiomode", {"mode": mode})

    async def reboot(self) -> None:
        """Reboot the processor."""
        await self._send_request("POST", "/v1/reboot")

    async def trigger_hpd(self) -> None:
        """Trigger Hot Plug Detect (HPD) for EDID/display refresh."""
        await self._send_request("POST", "/v1/hdmi/output/hpd")

    async def set_trigger(self, state: bool) -> None:
        """Enable or disable 12V trigger output."""
        val = "on" if state else "off"
        await self._send_request("POST", "/v1/trigger/output", {"state": val})

    async def get_input_bass(self, name: str) -> float:
        """Get bass level for a specific input source (-12 to +12 dB)."""
        res = await self._send_request("GET", f"/api/atlas/input/{name}/bass/")
        if isinstance(res, dict):
            return float(res.get("bass", res.get("level", 0.0)))
        return 0.0

    async def set_input_bass(self, name: str, level: float) -> None:
        """Set bass level for a specific input source."""
        await self._send_request("POST", f"/api/atlas/input/{name}/bass/{level}")

    async def get_input_treble(self, name: str) -> float:
        """Get treble level for a specific input source (-12 to +12 dB)."""
        res = await self._send_request("GET", f"/api/atlas/input/{name}/treb/")
        if isinstance(res, dict):
            return float(res.get("treble", res.get("level", 0.0)))
        return 0.0

    async def set_input_treble(self, name: str, level: float) -> None:
        """Set treble level for a specific input source."""
        await self._send_request("POST", f"/api/atlas/input/{name}/treb/{level}")

    async def set_display_brightness(self, level: int) -> None:
        """Set front panel display brightness percentage."""
        await self._send_request("POST", "/v1/displaybrightness", {"level": level})