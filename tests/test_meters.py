"""LevelMeters and the stream format, against an in-memory stand-in for the processor."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.hyperion_apr16.meters import (
    LevelMeters,
    decode_levels,
    encode_request,
    split_envelopes,
)

from .meter_fakes import FakeStream, envelope, quiet, reading, wait_until


@pytest.fixture
def stream() -> FakeStream:
    return FakeStream()


def make_meters(stream: FakeStream, **options: float) -> LevelMeters:
    """Meters with no throttle and quick reconnects, unless a test says otherwise."""
    options = {"publish_interval": 0.0, "reconnect_min": 0.01, "reconnect_max": 0.02, **options}
    return LevelMeters(stream, **options)


# --------------------------------------------------------------------------- the stream format


def test_the_request_asks_for_every_channel_at_the_update_rate() -> None:
    assert encode_request(100) == b"\x00\x00\x00\x00\x02\x10\x64"


def test_levels_are_read_with_negative_numbers() -> None:
    assert decode_levels(reading([-96, -11, 0, -1])) == [-96, -11, 0, -1]


def test_levels_sent_one_per_field_are_read_too() -> None:
    assert decode_levels(b"\x08\x05\x08" + b"\xf6\xff\xff\xff\xff\xff\xff\xff\xff\x01") == [5, -10]


def test_a_partial_envelope_waits_for_the_rest() -> None:
    whole = envelope(reading([-50] * 20))
    buffer = bytearray(whole[:7])

    assert list(split_envelopes(buffer)) == []
    buffer.extend(whole[7:] + envelope(b"", flags=2))

    assert list(split_envelopes(buffer)) == [(0, reading([-50] * 20)), (2, b"")]
    assert not buffer


# --------------------------------------------------------------------------- readings


async def test_nothing_is_requested_until_started(stream: FakeStream) -> None:
    meters = make_meters(stream)

    await asyncio.sleep(0.05)

    assert not meters.active
    assert stream.opened == 0
    assert meters.levels == [None] * 16


async def test_the_first_reading_shows_all_sixteen_outputs(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)

    stream.send(quiet(ch1=-20, ch16=-30, ch17=-5))
    await wait_until(lambda: meters.levels[0] is not None)

    assert meters.levels == [-20] + [-96] * 14 + [-30]
    assert meters.peaks == meters.levels
    await meters.stop()


async def test_the_stream_is_opened_with_the_update_rate(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)

    assert stream.bodies == [encode_request(100)]
    await meters.stop()


async def test_a_level_only_changes_once_it_has_moved_three_db(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-40))
    await wait_until(lambda: meters.levels[0] == -40)

    stream.send(quiet(ch1=-42))
    stream.send(quiet(ch1=-38))
    stream.send(quiet(ch1=-37))
    await wait_until(lambda: meters.levels[0] == -37)

    assert meters.levels[0] == -37
    await meters.stop()


async def test_changes_are_shown_no_more_often_than_the_interval(stream: FakeStream) -> None:
    meters = make_meters(stream, publish_interval=0.3)
    changes = []
    meters.add_listener(lambda: changes.append(list(meters.levels)))
    meters.start()
    await wait_until(lambda: stream.opened)
    changes.clear()

    for level in (-60, -50, -40, -30):
        stream.send(quiet(ch1=level))
    await asyncio.sleep(0.1)

    assert len(changes) == 1  # only the first of the four
    await meters.stop()


async def test_a_short_spike_is_held_even_when_it_is_not_shown_at_once(stream: FakeStream) -> None:
    meters = make_meters(stream, publish_interval=0.1)
    meters.start()
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch2=-50))
    await wait_until(lambda: meters.peaks[1] == -50)

    stream.send(quiet(ch2=-3))  # inside the interval: not published yet
    stream.send(quiet(ch2=-50))
    await asyncio.sleep(0.15)
    stream.send(quiet(ch2=-50))
    await wait_until(lambda: meters.peaks[1] == -3)

    assert meters.peaks[1] == -3
    await meters.stop()


async def test_a_reading_without_all_the_outputs_is_ignored(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)

    stream.send([-20] * 5)
    stream.send_raw(envelope(b"\x0a\xff"))  # cut off in the middle of a number
    stream.send(quiet(ch3=-33))
    await wait_until(lambda: meters.levels[2] is not None)

    assert meters.levels[2] == -33
    await meters.stop()


async def test_a_reading_split_over_two_chunks_is_still_read(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)

    data = envelope(reading(quiet(ch4=-12)))
    stream.send_raw(data[:9])
    stream.send_raw(data[9:])
    await wait_until(lambda: meters.levels[3] is not None)

    assert meters.levels[3] == -12
    await meters.stop()


# --------------------------------------------------------------------------- start and stop


async def test_stopping_closes_the_stream_and_clears_the_levels_but_keeps_the_peaks(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-9))
    await wait_until(lambda: meters.levels[0] == -9)

    await meters.stop()

    assert not meters.active
    assert stream.closed == 1
    assert meters.levels == [None] * 16
    assert meters.peaks[0] == -9


async def test_resetting_the_peaks_clears_them_and_they_start_again(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-9))
    await wait_until(lambda: meters.peaks[0] == -9)

    meters.reset_peaks()
    assert meters.peaks == [None] * 16

    stream.send(quiet(ch1=-30))
    await wait_until(lambda: meters.peaks[0] == -30)
    await meters.stop()


async def test_the_reading_after_a_reset_is_shown_without_waiting_for_the_interval(stream: FakeStream) -> None:
    meters = make_meters(stream, publish_interval=1000)
    meters.start()
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-9))
    await wait_until(lambda: meters.peaks[0] == -9)

    meters.reset_peaks()
    stream.send(quiet(ch1=-30))
    await wait_until(lambda: meters.peaks[0] == -30)
    await meters.stop()

async def test_the_meters_switch_themselves_off(stream: FakeStream) -> None:
    meters = make_meters(stream, auto_off=0.1)
    meters.start()
    await wait_until(lambda: stream.opened)

    await wait_until(lambda: not meters.active and stream.closed == 1)

    assert meters.levels == [None] * 16


async def test_starting_again_gives_the_meters_a_fresh_auto_off_period(stream: FakeStream) -> None:
    meters = make_meters(stream, auto_off=0.3)
    meters.start()
    await asyncio.sleep(0.2)
    meters.start()
    await asyncio.sleep(0.2)

    assert meters.active
    assert stream.opened == 1  # not reconnected
    await meters.stop()


async def test_listeners_hear_about_changes_until_removed(stream: FakeStream) -> None:
    meters = make_meters(stream)
    heard = []
    remove = meters.add_listener(lambda: heard.append(meters.active))

    meters.start()
    assert heard == [True]

    remove()
    await meters.stop()
    assert heard == [True]


# --------------------------------------------------------------------------- trouble


async def test_it_reconnects_after_a_failed_connection(stream: FakeStream) -> None:
    stream.fail_next = OSError("unreachable")
    meters = make_meters(stream)

    meters.start()
    await wait_until(lambda: stream.opened == 1)
    stream.send(quiet(ch1=-44))
    await wait_until(lambda: meters.levels[0] == -44)

    assert meters.active
    await meters.stop()


async def test_it_reconnects_when_the_processor_closes_the_stream(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened == 1)

    stream.end()
    await wait_until(lambda: stream.opened == 2)

    assert meters.active
    await meters.stop()


async def test_it_reconnects_after_the_closing_message(stream: FakeStream) -> None:
    meters = make_meters(stream)
    meters.start()
    await wait_until(lambda: stream.opened == 1)

    stream.send_raw(envelope(b"{}", flags=2))
    await wait_until(lambda: stream.opened == 2)
    await meters.stop()


async def test_a_silent_stream_is_replaced(stream: FakeStream) -> None:
    meters = make_meters(stream, silence_timeout=0.1)
    meters.start()

    await wait_until(lambda: stream.opened == 2)
    await meters.stop()
