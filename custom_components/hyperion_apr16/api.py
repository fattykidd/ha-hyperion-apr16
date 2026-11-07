"""API client for AudioControl Hyperion APR-16 Atlas service (Dirac controls)."""

from __future__ import annotations

import logging

from aiohttp import ClientError, ClientSession

_LOG = logging.getLogger(__name__)


class AtlasDiracController:
    """Async gRPC-web Connect-RPC client for AudioControl Atlas service on port 80."""

    def __init__(self, host: str, port: int = 80, session: ClientSession | None = None, session_cookie: str | None = None) -> None:
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
        
        # Wrap in Connect-RPC 5-byte binary framing envelope if payload exists
        if inner_payload:
            framed_content = b"\x00" + len(inner_payload).to_bytes(4, "big") + inner_payload
        else:
            framed_content = b""

        try:
            if self._session:
                async with self._session.post(
                    url,
                    headers=self.headers,
                    cookies=self.cookies,
                    data=framed_content,
                    timeout=10,
                ) as response:
                    response.raise_for_status()
                    return await response.text()
            else:
                _LOG.error("No aiohttp session provided to AtlasDiracController")
                raise RuntimeError("Aiohttp session missing")
        except (ClientError, TimeoutError, OSError) as err:
            _LOG.error("Atlas RPC command failed for %s: %s", url, err)
            raise

    async def get_filter_slots(self) -> str:
        """Fetch raw response containing filter slot descriptions."""
        return await self._post_command("GetDiracFilterSlots", b"")

    async def set_filter_slot(self, slot_index: int) -> bool:
        """Set the active Dirac filter slot by index (e.g., 0, 1, 2)."""
        inner_payload = bytes([0x10, slot_index])
        res = await self._post_command("SetDiracFilterSlot", inner_payload)
        return res is not None

    async def set_dirac_filtering(self, enabled: bool) -> bool:
        """Enable or disable master Dirac filtering."""
        inner_payload = (
            bytes([0x08, 0x01, 0x10, 0x01, 0x18, 0x01])
            if enabled
            else bytes([0x08, 0x00, 0x10, 0x01, 0x18, 0x01])
        )
        res = await self._post_command("SetDiracFiltering", inner_payload)
        return res is not None