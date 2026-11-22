"""StateStream against an in-memory stand-in for the processor's /ws/state endpoint.

The stand-in waits to be told which kind of state is wanted, answers with the current state (as JSON inside
a string, like the device) and then reports changes. No network is involved.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import NamedTuple

import aiohttp

from custom_components.hyperion_apr16.stream import StateStream

AUDIO = {"power": True, "volume": 36, "mute": False, "audio_mode": "native", "timestamp": 1000}


class Message(NamedTuple):
    """What aiohttp's WebSocket hands back from receive()."""

    type: aiohttp.WSMsgType
    data: str | None = None


async def wait_until(condition: Callable[[], object], timeout: float = 3.0) -> None:
    """Wait for something that happens in the background."""
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


class FakeSocket:
    """One connection to the processor, seen from the integration's side."""

    def __init__(self, processor: FakeProcessor) -> None:
        self._processor = processor
        self._inbox: asyncio.Queue[Message] = asyncio.Queue()
        self.kind: str | None = None
        self.closed = False

    async def send_str(self, text: str) -> None:
        """The integration says which kind of state it wants; the processor answers with the current one."""
        self.kind = json.loads(text)["request"]
        self._processor.requests.append(self.kind)
        self.push_state(self._processor.state)

    async def receive(self, timeout: float | None = None) -> Message:
        async with asyncio.timeout(timeout):
            return await self._inbox.get()

    async def close(self) -> None:
        self.closed = True

    def push_state(self, state: dict) -> None:
        self.push_text(json.dumps({"request": self.kind, "state": json.dumps(state)}))

    def push_text(self, text: str) -> None:
        self._inbox.put_nowait(Message(aiohttp.WSMsgType.TEXT, text))

    def hang_up(self) -> None:
        self._inbox.put_nowait(Message(aiohttp.WSMsgType.CLOSED))


class FakeProcessor:
    """A /ws/state endpoint. ``state`` is what it reports to a new connection."""

    def __init__(self, state: dict | None = None) -> None:
        self.state = dict(state if state is not None else AUDIO)
        self.requests: list[str] = []  # the kind each connection asked for
        self.connections: list[FakeSocket] = []
        self.refusing = False  # connections fail, like firmware that has no /ws/state

    async def connect(self) -> FakeSocket:
        if self.refusing:
            raise ConnectionError("connection refused")
        socket = FakeSocket(self)
        self.connections.append(socket)
        return socket

    def report(self, **changes) -> None:
        """A change on the processor: every open connection is sent the complete new state."""
        self.state.update(changes)
        for socket in self.connections:
            if not socket.closed:
                socket.push_state(self.state)

    def heartbeat(self) -> None:
        for socket in self.connections:
            if not socket.closed:
                socket.push_text(json.dumps({"heartbeat": True}))

    def hang_up(self) -> None:
        for socket in self.connections:
            socket.hang_up()


class Rig:
    """A fake processor, a stream following it, and what the stream reported."""

    def __init__(self, **options) -> None:
        self.processor = FakeProcessor()
        self.states: list[dict] = []
        self.stream = StateStream(
            "audio",
            self.processor.connect,
            self.states.append,
            reconnect_min=0.02,
            reconnect_max=0.05,
            **options,
        )


def make_rig(*, start: bool = True, **options) -> Rig:
    rig = Rig(**options)
    if start:
        rig.stream.start()
    return rig


# --------------------------------------------------------------------------- what is asked for and what arrives


async def test_the_kind_of_state_wanted_is_sent_and_the_first_state_arrives() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)

        assert rig.processor.requests == ["audio"]
        assert rig.states[0]["volume"] == 36
    finally:
        await rig.stream.stop()


async def test_the_state_is_decoded_and_its_timestamp_dropped() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)

        assert rig.states == [{"power": True, "volume": 36, "mute": False, "audio_mode": "native"}]
    finally:
        await rig.stream.stop()


async def test_a_state_that_only_differs_by_timestamp_is_not_reported_again() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)

        for second in range(1001, 1006):  # the audio stream repeats itself every second
            rig.processor.report(timestamp=second)
        rig.processor.report(volume=40)
        await wait_until(lambda: len(rig.states) == 2)

        assert [state["volume"] for state in rig.states] == [36, 40]
    finally:
        await rig.stream.stop()


async def test_messages_that_are_not_states_are_ignored() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)
        socket = rig.processor.connections[0]

        rig.processor.heartbeat()
        socket.push_text("not json")
        socket.push_text(json.dumps(["a", "list"]))
        socket.push_text(json.dumps({"request": "audio", "state": "not json either"}))
        socket.push_text(json.dumps({"request": "audio", "state": "[1, 2]"}))
        rig.processor.report(volume=41)
        await wait_until(lambda: len(rig.states) == 2)

        assert rig.states[1]["volume"] == 41
        assert rig.stream.live
    finally:
        await rig.stream.stop()


async def test_a_listener_that_fails_does_not_end_the_stream() -> None:
    rig = make_rig(start=False)
    seen: list[int] = []

    def listener(state: dict) -> None:
        seen.append(state["volume"])
        raise RuntimeError("the listener is broken")

    rig.stream._on_state = listener
    rig.stream.start()
    try:
        await wait_until(lambda: seen)
        rig.processor.report(volume=50)
        await wait_until(lambda: seen == [36, 50])
        assert len(rig.processor.requests) == 1  # it never had to reconnect
    finally:
        await rig.stream.stop()


# --------------------------------------------------------------------------- whether the stream can be trusted


async def test_a_stream_is_live_only_while_connected() -> None:
    rig = make_rig(start=False)

    assert not rig.stream.live

    rig.stream.start()
    await wait_until(lambda: rig.stream.live)

    await rig.stream.stop()
    assert not rig.stream.live


async def test_starting_twice_opens_one_connection() -> None:
    rig = make_rig()
    try:
        rig.stream.start()
        await wait_until(lambda: rig.stream.live)
        await asyncio.sleep(0.1)

        assert rig.processor.requests == ["audio"]
    finally:
        await rig.stream.stop()


async def test_stopping_closes_the_connection() -> None:
    rig = make_rig()
    await wait_until(lambda: rig.stream.live)

    await rig.stream.stop()

    assert rig.processor.connections[0].closed


async def test_a_silent_connection_is_replaced() -> None:
    rig = make_rig(silence_timeout=0.2)
    try:
        await wait_until(lambda: len(rig.processor.requests) == 1)
        await asyncio.sleep(0.1)
        assert rig.stream.live

        await wait_until(lambda: len(rig.processor.requests) == 2)  # nothing heard for 0.2 s: it reconnected
        await wait_until(lambda: len(rig.states) == 2)  # and the new connection's state was reported
    finally:
        await rig.stream.stop()


async def test_heartbeats_keep_a_quiet_connection_alive() -> None:
    rig = make_rig(silence_timeout=0.3)
    try:
        await wait_until(lambda: rig.stream.live)

        for _ in range(6):
            await asyncio.sleep(0.1)
            rig.processor.heartbeat()

        assert rig.processor.requests == ["audio"]
        assert rig.stream.live
    finally:
        await rig.stream.stop()


# --------------------------------------------------------------------------- reconnecting


async def test_it_reconnects_when_the_processor_hangs_up() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)

        rig.processor.state["volume"] = 44  # changed while the connection was down
        rig.processor.hang_up()

        await wait_until(lambda: len(rig.processor.requests) == 2)
        await wait_until(lambda: rig.states[-1]["volume"] == 44)
        assert rig.stream.live
    finally:
        await rig.stream.stop()


async def test_an_unchanged_state_is_reported_again_after_reconnecting() -> None:
    rig = make_rig()
    try:
        await wait_until(lambda: rig.states)
        rig.processor.hang_up()

        await wait_until(lambda: len(rig.states) == 2)  # anything could have changed meanwhile, so say so
        assert rig.states[0] == rig.states[1]
    finally:
        await rig.stream.stop()


async def test_a_processor_that_cannot_be_reached_is_retried_until_it_can() -> None:
    rig = make_rig(start=False)
    rig.processor.refusing = True
    rig.stream.start()
    try:
        await asyncio.sleep(0.2)  # several refused attempts
        assert not rig.stream.live
        assert rig.states == []

        rig.processor.refusing = False

        await wait_until(lambda: rig.stream.live)
        await wait_until(lambda: rig.states)
    finally:
        await rig.stream.stop()
