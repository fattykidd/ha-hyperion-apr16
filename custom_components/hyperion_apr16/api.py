class AtlasDiracController:
    def __init__(self, host: str, port: int = 80, session_cookie: str = None):
        self.host = host
        self.port = port  # Defaults to 80 for Atlas service endpoints
        self.base_url = f"http://{host}:{port}/commands.v1.AtlasService"
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

    async def _post_command(self, endpoint: str, inner_payload: bytes = b"") -> httpx.Response:
        url = f"{self.base_url}/{endpoint}"
        framed_content = b"\x00" + len(inner_payload).to_bytes(4, "big") + inner_payload if inner_payload else b""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                cookies=self.cookies,
                content=framed_content,
                timeout=10.0,
            )
        return response

    async def get_filter_slots(self) -> str:
        response = await self._post_command("GetDiracFilterSlots")
        return response.text

    async def set_filter_slot(self, slot_index: int) -> bool:
        inner_payload = bytes([0x10, slot_index])
        response = await self._post_command("SetDiracFilterSlot", inner_payload)
        return response.status_code == 200

    async def set_dirac_filtering(self, enabled: bool) -> bool:
        inner_payload = bytes([0x08, 0x01, 0x10, 0x01, 0x18, 0x01]) if enabled else bytes([0x08, 0x00, 0x10, 0x01, 0x18, 0x01])
        response = await self._post_command("SetDiracFiltering", inner_payload)
        return response.status_code == 200