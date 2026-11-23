"""An in-memory stand-in for the processor's level-meter stream, shared by the meter tests."""

from __future__ import annotations

import asyncio
import struct
from collections.abc import AsyncIterator, Callable
from typing import Self


def varint(value: int) -> bytes:
    """Encode a number as the processor does; negative numbers are 64-bit two's complement."""
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def reading(levels: list[int], timestamp: int = 1_700_000_000_000) -> bytes:
    """One ``VUMeterStreamResponse``: the levels packed in field 1 and a timestamp in field 2."""
    packed = b"".join(varint(level) for level in levels)
    return b"\x0a" + varint(len(packed)) + packed + b"\x10" + varint(timestamp)


def envelope(message: bytes, flags: int = 0) -> bytes:
    """Wrap a message the way the Connect protocol streams it."""
    return bytes([flags]) + struct.pack(">I", len(message)) + message


def quiet(**loud: int) -> list[int]:
    """Twenty channels of silence, with ``ch1=-20`` style overrides (1-based channel numbers)."""
    levels = [-96] * 20
    for name, level in loud.items():
        levels[int(name.removeprefix("ch")) - 1] = level
    return levels


class FakeStream:
    """
    Stands in for ``Apr16.async_open_meter_stream``.

    Calling it returns the response context. Readings are pushed with ``send``; ``end`` closes the stream and
    ``fail_next`` makes the next connection attempt fail.
    """

    def __init__(self) -> None:
        self.opened = 0
        self.closed = 0
        self.bodies: list[bytes] = []
        self.fail_next: Exception | None = None
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.content = self

    def __call__(self, body: bytes) -> FakeStream:
        self.bodies.append(body)
        self._chunks = asyncio.Queue()
        return self

    async def __aenter__(self) -> Self:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        self.opened += 1
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed += 1

    def raise_for_status(self) -> None:
        """The fake processor always answers 200."""

    async def iter_any(self) -> AsyncIterator[bytes]:
        """Hand over what ``send`` queued, until ``end``."""
        while (chunk := await self._chunks.get()) is not None:
            yield chunk

    def send(self, levels: list[int], flags: int = 0) -> None:
        """The processor sends one reading."""
        self._chunks.put_nowait(envelope(reading(levels), flags))

    def send_raw(self, data: bytes) -> None:
        """The processor sends bytes, however they are cut up."""
        self._chunks.put_nowait(data)

    def end(self) -> None:
        """The processor closes the stream."""
        self._chunks.put_nowait(None)


async def wait_until(condition: Callable[[], object], timeout: float = 3.0) -> None:
    """Wait for something that happens in the background."""
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)
