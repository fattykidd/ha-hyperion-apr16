"""
Live level meters of the AudioControl Hyperion APR-16.

The meters are a server-streaming call, so they use the processor's Connect protocol on port 80 rather than
REST. One POST opens the stream and the processor then sends a reading every few hundred milliseconds, each one
wrapped in an envelope: one flag byte (bit 0x02 marks the closing message), a 4-byte big-endian length and a
protobuf message.

- Request: ``update_rate_ms`` (field 2). Leaving the channel list out asks for every channel.
- Response: ``channel_levels_db`` (field 1, packed), one whole-dB value per output, -96 meaning silence.
  The processor reports 20 values, of which the first 16 are the XLR outputs. Meter channel N is output N.

LevelMeters starts and stops that stream on demand, keeps a peak-hold per output, and hands entities values
that are throttled, so a reading arriving several times a second doesn't turn into several state changes a
second.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections.abc import Callable, Iterator
from typing import Any

from .const import (
    METER_AUTO_OFF,
    METER_CHANNELS,
    METER_LEVEL_STEP_DB,
    METER_PUBLISH_INTERVAL,
    METER_SILENCE_TIMEOUT,
    METER_UPDATE_MS,
    STREAM_RECONNECT_MAX,
    STREAM_RECONNECT_MIN,
    STREAM_STABLE_AFTER,
)

_LOG = logging.getLogger(__name__)

# What the device sends is a stream of envelopes; this opens one and returns the HTTP response's context.
MeterOpener = Callable[[bytes], Any]

_END_OF_STREAM = 0x02


# --------------------------------------------------------------------------- the wire format


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return result, pos


def _as_signed(value: int) -> int:
    """Negative numbers are sent as 64-bit two's complement."""
    value &= (1 << 64) - 1
    return value - (1 << 64) if value >> 63 else value


def encode_request(update_rate_ms: int) -> bytes:
    """The body of the request that opens the stream: one envelope holding the update rate."""
    message = b"\x10" + _encode_varint(update_rate_ms)
    return b"\x00" + struct.pack(">I", len(message)) + message


def decode_levels(message: bytes) -> list[int]:
    """The ``channel_levels_db`` of one reading (packed, or one value per field)."""
    levels: list[int] = []
    pos = 0
    while pos < len(message):
        key, pos = _decode_varint(message, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _decode_varint(message, pos)
            if field == 1:
                levels.append(_as_signed(value))
        elif wire == 2:
            length, pos = _decode_varint(message, pos)
            chunk, pos = message[pos : pos + length], pos + length
            if field == 1:
                inner = 0
                while inner < len(chunk):
                    value, inner = _decode_varint(chunk, inner)
                    levels.append(_as_signed(value))
        elif wire == 1:
            pos += 8
        elif wire == 5:
            pos += 4
        else:
            raise ValueError(f"unexpected wire type {wire}")
    return levels


def split_envelopes(buffer: bytearray) -> Iterator[tuple[int, bytes]]:
    """Take every complete (flags, message) out of the buffer, leaving a partial one for next time."""
    while len(buffer) >= 5:
        flags = buffer[0]
        (length,) = struct.unpack(">I", bytes(buffer[1:5]))
        if len(buffer) < 5 + length:
            return
        message = bytes(buffer[5 : 5 + length])
        del buffer[: 5 + length]
        yield flags, message


# --------------------------------------------------------------------------- the meters


class LevelMeters:
    """
    Runs the level-meter stream when asked to, and keeps what entities show.

    ``levels`` and ``peaks`` hold one whole-dB value per output, or None when there is nothing to show. They
    are the published values: a level only changes once it has moved by ``METER_LEVEL_STEP_DB`` and nothing is
    published more than once per ``METER_PUBLISH_INTERVAL``. Peaks are tracked on every reading, so a short
    spike is never missed, and they are kept when the meters stop until ``reset_peaks`` is called.
    """

    def __init__(
        self,
        open_stream: MeterOpener,
        *,
        auto_off: float = METER_AUTO_OFF,
        silence_timeout: float = METER_SILENCE_TIMEOUT,
        reconnect_min: float = STREAM_RECONNECT_MIN,
        reconnect_max: float = STREAM_RECONNECT_MAX,
        publish_interval: float = METER_PUBLISH_INTERVAL,
        log_id: str = "",
    ) -> None:
        """
        Create the meters. Nothing is requested from the processor until start() is called.

        :param open_stream: given the request body, returns the HTTP response context of the stream
        :param auto_off: seconds after which the meters switch themselves off
        :param silence_timeout: seconds without a reading before the connection is replaced
        :param reconnect_min: first delay before reconnecting, doubled after each failure
        :param reconnect_max: longest delay before reconnecting
        :param publish_interval: shortest time between two published changes
        """
        self._open_stream = open_stream
        self._auto_off = auto_off
        self._silence_timeout = silence_timeout
        self._reconnect_min = reconnect_min
        self._reconnect_max = reconnect_max
        self._publish_interval = publish_interval
        self._log_id = log_id or "meters"

        self.levels: list[int | None] = [None] * METER_CHANNELS
        self.peaks: list[int | None] = [None] * METER_CHANNELS
        self._held_peaks: list[int | None] = [None] * METER_CHANNELS  # every reading, not yet published

        self._active = False
        self._task: asyncio.Task | None = None
        self._timer: asyncio.TimerHandle | None = None
        self._last_publish = float("-inf")
        self._listeners: list[Callable[[], None]] = []

    @property
    def active(self) -> bool:
        """True from start() until the meters are stopped, by the user, the timer or shutdown."""
        return self._active

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call ``listener`` whenever the published values change. Returns a function that removes it."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def start(self) -> None:
        """Start the meters, or give them a fresh auto-off period if they are already running."""
        loop = asyncio.get_running_loop()
        if self._timer is not None:
            self._timer.cancel()
        self._timer = loop.call_later(self._auto_off, self._switch_off)

        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._run(), name="hyperion-level-meters")
        self._notify()

    async def stop(self) -> None:
        """Stop the meters and close the stream. The peaks stay."""
        was_active, self._active = self._active, False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.levels = [None] * METER_CHANNELS
        if was_active:
            self._notify()

    def reset_peaks(self) -> None:
        """Forget the held peaks. They start again from the next reading."""
        self.peaks = [None] * METER_CHANNELS
        self._held_peaks = [None] * METER_CHANNELS
        self._last_publish = float("-inf")
        self._notify()

    # ------------------------------------------------------------------

    def _switch_off(self) -> None:
        """The auto-off timer ran out."""
        _LOG.debug("[%s] Switching the level meters off after %s s", self._log_id, self._auto_off)
        self._timer = None
        asyncio.get_running_loop().create_task(self.stop())

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOG.exception("[%s] A level meter listener failed", self._log_id)

    async def _run(self) -> None:
        """Keep the stream open while the meters are on, reconnecting after every failure."""
        delay = self._reconnect_min
        warned = False

        while True:
            started = time.monotonic()
            try:
                await self._follow()
                reason = "the processor closed the stream"
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - whatever went wrong, the answer is to reconnect
                reason = repr(err) if isinstance(err, TimeoutError) else str(err)

            if time.monotonic() - started >= STREAM_STABLE_AFTER:
                delay = self._reconnect_min
                warned = False

            if warned:
                _LOG.debug("[%s] The level meters are still down: %s", self._log_id, reason)
            else:
                _LOG.warning("[%s] Lost the level meters (%s), retrying", self._log_id, reason)
                warned = True

            await asyncio.sleep(delay)
            delay = min(delay * 2, self._reconnect_max)

    async def _follow(self) -> None:
        """One connection, from opening it until it ends or goes quiet."""
        async with self._open_stream(encode_request(METER_UPDATE_MS)) as response:
            response.raise_for_status()
            _LOG.debug("[%s] Following the level meters", self._log_id)

            buffer = bytearray()
            chunks = response.content.iter_any()
            while True:
                async with asyncio.timeout(self._silence_timeout):
                    chunk = await anext(chunks, None)
                if chunk is None:
                    return
                buffer.extend(chunk)
                for flags, message in split_envelopes(buffer):
                    if flags & _END_OF_STREAM:
                        return
                    self._handle(message)

    def _handle(self, message: bytes) -> None:
        """Take one reading: update the peaks, and publish what has changed enough to matter."""
        try:
            readings = decode_levels(message)[:METER_CHANNELS]
        except (ValueError, IndexError):
            _LOG.debug("[%s] Ignoring a reading that can't be decoded", self._log_id)
            return
        if len(readings) < METER_CHANNELS:
            return

        for channel, level in enumerate(readings):
            held = self._held_peaks[channel]
            if held is None or level > held:
                self._held_peaks[channel] = level

        now = time.monotonic()
        if now - self._last_publish < self._publish_interval:
            return

        changed = False
        for channel, level in enumerate(readings):
            shown = self.levels[channel]
            if shown is None or abs(level - shown) >= METER_LEVEL_STEP_DB:
                self.levels[channel] = level
                changed = True
        if self.peaks != self._held_peaks:
            self.peaks = list(self._held_peaks)
            changed = True

        if changed:
            self._last_publish = now
            self._notify()
