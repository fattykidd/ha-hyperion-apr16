"""The device client's lookups that need several requests."""

from __future__ import annotations

from typing import Any, Self

from aiohttp import ClientConnectionError

from custom_components.hyperion_apr16.config import APR16Config
from custom_components.hyperion_apr16.device import Apr16


class FakeResponse:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self) -> dict[str, Any]:
        return self._body


class FakeSession:
    """Answers GET /api/atlas/input/name?input=N from a table; a missing entry is a lost connection."""

    def __init__(self, names: dict[int, dict[str, Any]]) -> None:
        self._names = names
        self.requests: list[str] = []

    def get(self, url: str, **_: Any) -> FakeResponse:
        self.requests.append(url)
        input_id = int(url.rsplit("=", 1)[1])
        if input_id not in self._names:
            raise ClientConnectionError("no answer")
        return FakeResponse(200, self._names[input_id])


def make_device(session: FakeSession) -> Apr16:
    config = APR16Config(identifier="id", name="APR", address="192.168.1.50", port=8080)
    return Apr16(device_config=config, session=session)


async def test_the_custom_input_names_are_collected() -> None:
    session = FakeSession({i: {"name": f"Input {i}"} for i in range(1, 17)})

    names = await make_device(session).async_get_input_names()

    assert names == {i: f"Input {i}" for i in range(1, 17)}
    assert session.requests[0] == "http://192.168.1.50:8080/api/atlas/input/name?input=1"


async def test_inputs_without_a_name_are_left_out() -> None:
    table = {i: {"name": ""} for i in range(1, 17)}
    table[3] = {"name": "Apple TV"}

    names = await make_device(FakeSession(table)).async_get_input_names()

    assert names == {3: "Apple TV"}


async def test_the_lookup_stops_when_the_processor_stops_answering() -> None:
    session = FakeSession({1: {"name": "Apple TV"}, 2: {"name": "PS5"}})

    names = await make_device(session).async_get_input_names()

    assert names == {1: "Apple TV", 2: "PS5"}
    assert len(session.requests) == 3  # input 3 got no answer, so it didn't go on to 4
