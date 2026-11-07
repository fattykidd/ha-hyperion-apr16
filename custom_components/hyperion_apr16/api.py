"""API client for AudioControl Hyperion APR-16 Atlas service."""
from __future__ import annotations

import logging

from aiohttp import ClientSession

_LOG = logging.getLogger(__name__)


class HyperionAPI:
    """Client for communicating with the Hyperion Atlas gRPC-web service."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        session: ClientSession | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/commands.v1.AtlasService"
        self._session = session
        self.session_cookie = session_cookie
        self.headers = {
            "Accept": "*/*",
            "Connect-Protocol-Version": "1",
            "Content-Type": "application/proto",
            "Origin": f"http://{host}:{port}",
            "Referer": f"http://{host}:{port}/",
            "User-Agent": "HomeAssistant-HyperionIntegration/1.0",
        }
        self.cookies = {
            "forceUpdate": "true",
            "atlas_served_asset_session": session_cookie or "",
        }

    async def _post_command(self, endpoint: str, inner_payload: bytes = b"") -> str:
        url = f"{self.base_url}/{endpoint}"
        framed_content = b"\x00" + len(inner_payload).to_bytes(4, "big") + inner_payload

        async with self._session.post(
            url,
            headers=self.headers,
            cookies=self.cookies,
            data=framed_content,
            timeout=10,
        ) as response:
            response.raise_for_status()
            return await response.text()

    async def set_dirac_filtering(self, enabled: bool) -> bool:
        inner_payload = b"\x08\x01\x10\x01\x18\x01" if enabled else b"\x10\x01\x18\x01"
        res = await self._post_command("SetDiracFiltering", inner_payload)
        return res is not None

    async def set_filter_slot(self, slot_index: int) -> bool:
        payload_map = {
            0: b"\x10\x01",
            1: b"\x08\x01\x10\x01",
            2: b"\x08\x02\x10\x01",
        }
        inner_payload = payload_map.get(slot_index, b"\x10\x01")
        res = await self._post_command("SetDiracFilterSlot", inner_payload)
        return res is not None