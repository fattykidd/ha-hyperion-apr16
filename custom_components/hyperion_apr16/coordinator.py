"""Data update coordinator for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helper import percent_to_db

_LOG = logging.getLogger(__name__)


class HyperionDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Hyperion data central polling."""

    def __init__(self, hass: HomeAssistant, device: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOG,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.device = device
        # Expose the dirac client reference if entities need direct access for commands
        self.client = getattr(device, "dirac_client", None)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Hyperion APR-16 processor."""
        try:
            # Fetch base status dict directly from Apr16 client in device.py
            data = await self.device.async_get_status()

            # Attach device property metadata
            data["host_ip"] = getattr(self.device, "host", None)

            # Calculate volume dB
            vol_val = data.get("volume", data.get("level", 0.0))
            if vol_val is not None:
                data["volume_db"] = round(percent_to_db(float(vol_val)), 1)

            # Get the current active input ID (fallback to 1 if not present)
            input_id = data.get("input_id", data.get("active_input_id", 1))
            data["input_id"] = input_id

            # Fetch live per-input audio settings from GET endpoints safely
            try:
                trim_resp = await self.device.async_get_trim(input_id)
                data["channel_trim"] = float(trim_resp.get("level", 0))
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch channel trim for input %s: %s", input_id, err)

            try:
                gain_resp = await self.device.async_get_gain(input_id)
                data["channel_gain"] = float(gain_resp.get("level", 0))
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch channel gain for input %s: %s", input_id, err)

            try:
                lipsync_resp = await self.device.async_get_lipsync(input_id)
                data["lipsync_delay"] = float(lipsync_resp.get("delayMs", 0))
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch lipsync delay for input %s: %s", input_id, err)

            try:
                version_resp = await self.device.async_get_version()
                data["firmware_version"] = version_resp.get("version", "1.2.0")
                data["git_commit"] = version_resp.get("gitCommit", "")
                data["build_time"] = version_resp.get("buildTime", "")
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.debug("Could not fetch version: %s", err)

            try:
                mac_resp = await self.device.async_get_macaddress()
                data["mac_address"] = mac_resp
            except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                _LOG.warning("Could not fetch MAC address (Error: %s %s)", type(err).__name__, err)
                data["mac_address"] = "00:00:00:00:00:00"

            # Fetch Dirac filter slots & status via port 80 Atlas client safely
            if self.client:
                try:
                    dirac_slots_raw = await self.client.get_filter_slots()
                    data["dirac_filter_slots_raw"] = dirac_slots_raw
                except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                    _LOG.debug("Could not fetch Dirac filter slots: %s", err)

            # Fetch dynamic user-defined input names from port 8080
            input_names = {}
            for inp_id in range(1, 9):
                try:
                    url = f"http://{getattr(self.device, 'host', '192.168.50.170')}:8080/api/atlas/input/name?input={inp_id}"
                    async with self.device._session.get(url, headers={"accept": "application/json"}, timeout=1.0) as resp:
                        if resp.status == 200:
                            res_json = await resp.json()
                            if name := res_json.get("name"):
                                input_names[inp_id] = name
                except (ClientError, TimeoutError, OSError) as err:
                    _LOG.warning("Failed to fetch input name for input %d: %s", inp_id, err)
                    break  # Stop querying if input ID doesn't exist
            data["input_names"] = input_names

            # Fetch and clean Dirac filter slots safely
            if self.client:
                try:
                    raw_slots = await self.client.get_filter_slots()
                    # Clean binary gRPC data into readable user slot names using regex
                    if isinstance(raw_slots, bytes):
                        text_data = raw_slots.decode("utf-8", errors="ignore")
                    else:
                        text_data = str(raw_slots)
                    
                    found_slots = re.findall(r'([0-9]+\s*dB\s+[a-zA-Z0-9\-\s]+|[a-zA-Z0-9\-\s]+current)', text_data)
                    cleaned_slots = [s.strip() for s in found_slots if len(s.strip()) > 2]
                    
                    data["dirac_filter_slots"] = list(dict.fromkeys(cleaned_slots)) if cleaned_slots else ["Slot 0", "Slot 1"]
                except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
                    _LOG.debug("Could not parse Dirac filter slots: %s", err)
                    data["dirac_filter_slots"] = ["Slot 0", "Slot 1"]

            return data
        except (ClientError, TimeoutError, OSError, KeyError, ValueError) as err:
            raise UpdateFailed(
                f"Error communicating with Hyperion APR-16: {err}"
            ) from err