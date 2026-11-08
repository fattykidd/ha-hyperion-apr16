"""API client for AudioControl Hyperion APR-16 processor."""

from __future__ import annotations

import logging
import re
from typing import Any

from aiohttp import ClientError, ClientSession

from .config import APR16Config
from .helper import percent_to_db

_LOG = logging.getLogger(__name__)


class Apr16:
    """Async REST API client for AudioControl Hyperion APR-16."""

    def __init__(
        self,
        host: str | None = None,
        port: int = 8080,
        session: ClientSession | None = None,
        device_config: APR16Config | None = None,
        session_cookie: str | None = None,
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
        
        # Port 80 explicit base URL for Connect-RPC / Atlas service endpoints
        self._atlas_base_url = f"http://{self.host}:80/commands.v1.AtlasService"
        self.session_cookie = session_cookie

    async def _send_request(self, method: str, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """Send an HTTP request to the APR-16 API using the shared session."""
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

    async def _send_atlas_request(self, endpoint: str, inner_payload: bytes = b"") -> str:
        """Send a direct binary protocol request to the port 80 Atlas service."""
        url = f"http://{self.host}:80/commands.v1.AtlasService/{endpoint}"
        
        headers = {
            "Accept": "*/*",
            "Connect-Protocol-Version": "1",
            "Content-Type": "application/proto",
            "Origin": f"http://{self.host}:80",
            "Referer": f"http://{self.host}:80/",
            "User-Agent": "HomeAssistant-HyperionIntegration/1.0",
        }
        
        cookies = {
            "forceUpdate": "true",
            "atlas_served_asset_session": self.session_cookie,
        }

        try:
            async with self._session.post(
                url, 
                headers=headers, 
                cookies=cookies, 
                data=inner_payload, 
                timeout=10
            ) as response:
                response_text = await response.text()
                if response.status >= 400:
                    _LOG.error("Atlas RPC error response for %s: %s", endpoint, response_text)
                response.raise_for_status()
                return response_text
        except (ClientError, TimeoutError, OSError) as err:
            _LOG.error("Atlas request failed for %s: %s", url, err)
            raise

    # --- Dirac Methods for Port 80 Atlas Service ---
    
    async def async_get_dirac_filter_slots(self) -> str:
        """Fetch Dirac filter slots for status updates."""
        try:
            return await self._send_atlas_request("GetDiracFilterSlots", b"")
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("GetDiracFilterSlots request failed: %s", err)
            return ""

    async def async_get_dirac_filter_slots_list(self) -> list[str]:
        """Get the list of clean Dirac filter slot names for the select platform."""
        try:
            response_text = await self._send_atlas_request("GetDiracFilterSlots", b"")
            # Extract text patterns matching the slot names
            raw_matches = re.findall(r'([0-9a-zA-Z\s]+current)', response_text)
            
            slot_names = []
            for match in raw_matches:
                # Remove ASCII control characters (like \x0b) and trim whitespace
                cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', match).strip()
                if cleaned and cleaned not in slot_names:
                    slot_names.append(cleaned)
                    
            return slot_names if slot_names else []
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("Failed to get Dirac filter slots list: %s", err)
            return []
    
    async def async_get_dirac_active_slot(self) -> int:
        """Query the hardware live for the active Dirac slot index."""

        url = f"http://{self.host}/commands.v1.AtlasService/GetDiracActiveSlot"
        headers = {
            "Content-Type": "application/proto",
            "connect-protocol-version": "1",
        }
        
        # Use self._session if available, otherwise fallback to self.session
        session = getattr(self, "_session", getattr(self, "session", None))
        if not session:
            _LOG.debug("GetDiracActiveSlot failed: No active aiohttp session found on device client")
            return 0

        try:
            async with session.post(url, headers=headers, data=b"", timeout=2.0) as response:
                body = await response.read()
                _LOG.debug(
                    "ISOLATED GetDiracActiveSlot -> status: %s | body: %r",
                    response.status,
                    body,
                )
                if response.status == 200:
                    if not body:
                        return 0
                    if len(body) >= 2 and body[0] == 0x08:
                        return body[1]
        except (TimeoutError, ClientError, OSError, KeyError, ValueError) as err:
            _LOG.debug("ISOLATED GetDiracActiveSlot failed: %s", err)
            
        return 0

    async def async_set_dirac_filter_slot(self, slot_index: int) -> bool:
        """Switch active Dirac filter slot by index (0, 1, 2) using hex-decoded bytes."""
        # Slot 0: \x10\x01 -> hex: 1001
        # Slot 1: \x08\x01\x10\x01 -> hex: 08011001
        # Slot 2: \x08\x02\x10\x01 -> hex: 08021001
        payload_map = {
            0: bytes.fromhex("1001"),
            1: bytes.fromhex("08011001"),
            2: bytes.fromhex("08021001"),
        }
        inner_payload = payload_map.get(slot_index, bytes.fromhex("1001"))
        res = await self._send_atlas_request("SetDiracFilterSlot", inner_payload)
        return res is not None

    async def async_set_dirac_filtering(self, enabled: bool) -> bool:
        """Enable or disable master Dirac filtering using hex-decoded bytes."""
        # Filtering Off: \x10\x01\x18\x01 -> hex: 10011801
        # Filtering On:  \x08\x01\x10\x01\x18\x01 -> hex: 080110011801
        inner_payload = (
            bytes.fromhex("080110011801") if enabled else bytes.fromhex("10011801")
        )
        res = await self._send_atlas_request("SetDiracFiltering", inner_payload)
        return res is not None

    # --- Existing Apr16 Methods Below ---
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

        power = False
        if isinstance(power_res, dict):
            val = power_res.get("state", False)
            power = str(val).lower() in ("1", "true", "on")

        volume_percent = 0.0
        volume_db = -127.5
        
        if isinstance(vol_res, dict):
            volume_percent = float(vol_res.get("level", 0.0))
            volume_db = round(percent_to_db(volume_percent), 1)

        mute = False
        if isinstance(mute_res, dict):
            mute = bool(mute_res.get("state", mute_res.get("mute", False)))

        active_input = "HDMI 1"
        input_id = 1
        if isinstance(input_res, dict):
            active_input = input_res.get("input", input_res.get("name", "HDMI 1"))
            input_id = input_res.get("inputId", 1)

        bass_level = await self.get_input_bass(input_id)
        treble_level = await self.get_input_treble(input_id)

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
            val = trigger_res.get("enabled", trigger_res.get("state", trigger_res.get("value", False)))
            trigger_state = bool(val) if isinstance(val, bool) else str(val).lower() in ("1", "true", "on")

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

        # Fetch Dirac slots safely during status updates
        dirac_slots = ""
        try:
            dirac_slots = await self.async_get_dirac_filter_slots()
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            _LOG.debug("Could not fetch Dirac filter slots: %s", err)

        return {
            "power": power,
            "volume": volume_percent,
            "volume_db": volume_db,
            "mute": mute,
            "active_input": active_input,
            "input_id": input_id,
            "bass": bass_level,
            "treble": treble_level,
            "audio_mode": audio_mode,
            "brightness": brightness,
            "trigger_state": trigger_state,
            "audio_format": audio_format,
            "audio_detail": audio_detail,
            "video_detail": video_detail,
            "temperature": temperature,
            "dirac_slots_raw": dirac_slots,
            "dirac_active": True,
            "dirac_slot": 0,
        }

    async def power_on(self) -> None:
        """Turn the processor power on."""
        await self._send_request("POST", "/v1/power", {"state": "1"})

    async def power_off(self) -> None:
        """Turn the processor power off."""
        await self._send_request("POST", "/v1/power", {"state": "0"})

    async def set_volume(self, level: float) -> None:
        """Set volume level (0-100)."""
        await self._send_request("POST", "/v1/vol", {"level": round(level)})

    async def set_mute(self, mute: bool) -> None:
        """Set mute state."""
        await self._send_request("POST", "/v1/mute", {"state": mute})

    async def set_active_input(self, input_id: int | str) -> None:
        """Set active input source on port 8080 using the string input ID."""
        payload = {"input": str(input_id)}
        await self._send_request("POST", "/api/atlas/input/active", payload)

    async def set_audio_mode(self, mode: str) -> None:
        """Set the audio processing mode."""
        await self._send_request("POST", "/v1/audiomode", {"mode": mode})

    async def reboot(self) -> None:
        """Reboot the processor."""
        url = f"{self._base_url}/v1/reboot"
        try:
            async with self._session.post(url, json={}, timeout=5):
                pass
        except (ClientError, TimeoutError, OSError) as err:
            _LOG.info("Reboot command sent; device restarted as expected: %s", err)
            
    async def trigger_hpd(self, state: bool = True) -> None:
        """Trigger Hot Plug Detect (HPD) for EDID/display refresh."""
        await self._send_request("POST", "/v1/hdmi/output/hpd", {"state": bool(state)})

    async def set_trigger(self, state: bool) -> None:
        """Enable or disable 12V trigger output."""
        await self._send_request("POST", "/v1/trigger/output", {"enabled": bool(state)})

    async def async_get_input_names(self) -> dict[int, str]:
        """Fetch user-defined input names from the port 8080 REST API."""
        input_map = {}
        # Use the client session already established on the device class
        for input_id in range(1, 9):  # Adjust range based on your total inputs
            url = f"http://{self.host}:8080/api/atlas/input/name?input={input_id}"
            try:
                async with self._session.get(url, headers={"accept": "application/json"}, timeout=2) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        name = data.get("name")
                        if name:
                            input_map[input_id] = name
            except (ClientError, TimeoutError, OSError):
                _LOG.warning("Failed to fetch input name for input %d: %s", input)
                continue
        return input_map

    async def get_input_bass(self, input_id: int | str) -> float:
        """Get bass level for a specific input (-12 to +12 dB)."""
        res = await self._send_request("GET", f"/api/atlas/input/{input_id}/bass")
        if isinstance(res, dict):
            return float(res.get("level", 0.0))
        return 0.0

    async def set_input_bass(self, input_id: int | str, level: float) -> None:
        """Set bass level for a specific input, ensuring integer values for path compatibility."""
        int_level = round(level)
        await self._send_request(
            "POST", f"/api/atlas/input/{input_id}/bass/{int_level}", {"inputId": 0}
        )

    async def get_input_treble(self, input_id: int | str) -> float:
        """Get treble level for a specific input (-12 to +12 dB)."""
        res = await self._send_request("GET", f"/api/atlas/input/{input_id}/treb")
        if isinstance(res, dict):
            return float(res.get("level", 0.0))
        return 0.0

    async def set_input_treble(self, input_id: int | str, level: float) -> None:
        """Set treble level for a specific input, ensuring integer values for path compatibility."""
        int_level = round(level)
        await self._send_request(
            "POST", f"/api/atlas/input/{input_id}/treb/{int_level}", {"inputId": 0}
        )

    async def set_display_brightness(self, level: int) -> None:
        """Set front panel display brightness percentage."""
        await self._send_request("POST", "/v1/displaybrightness", {"brightness": level})
    
    async def get_brightness(self) -> int:
        """Get panel brightness (0-100)."""
        res = await self._send_request("GET", "/v1/brightness")
        if isinstance(res, dict):
            return int(res.get("brightness", res.get("level", 100)))
        return 100

    async def set_brightness(self, level: float) -> None:
        """Set panel brightness (0-100)."""
        await self._send_request("POST", "/v1/displaybrightness", {"brightness": round(level)})

    async def set_input_lipsync_delay(self, input_id: int, delay_ms: int) -> None:
        """Set lipsync delay for a specific input via Atlas API."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/lipsync/{int(delay_ms)}"
        async with self._session.post(url, json={"inputId": 0}) as response:
            response.raise_for_status()

    async def set_input_channel_gain(self, input_id: int, gain_db: float) -> None:
        """Set input gain/trim for a specific input via Atlas API."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/gain/{int(gain_db)}"
        async with self._session.post(url, json={"inputId": 0}) as response:
            response.raise_for_status()

    async def set_input_channel_trim(self, input_id: int, trim_val: float) -> None:
        """Set input channel trim for a specific input via Atlas API."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/trim/{int(trim_val)}"
        async with self._session.post(url, json={"inputId": 0}) as response:
            response.raise_for_status()

    async def async_get_trim(self, input_id: int) -> dict:
        """Get input channel trim."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/trim"
        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def async_get_gain(self, input_id: int) -> dict:
        """Get input gain."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/gain"
        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def async_get_lipsync(self, input_id: int) -> dict:
        """Get input lipsync delay."""
        url = f"{self._base_url}/api/atlas/input/{input_id}/lipsync"
        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def async_get_version(self) -> dict[str, Any]:
        """Fetch firmware version from the device."""
        url = f"{self._base_url}/v1/version"
        async with self._session.get(url, headers={"Content-Type": "application/json"}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def async_get_macaddress(self) -> str:
        """Fetch MAC address from the device."""
        url = f"{self._base_url}/v1/mac"
        async with self._session.get(url, headers={"Content-Type": "application/json"}) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("mac", "00:00:00:00:00:00")