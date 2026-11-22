"""The coordinator: live updates from the streams, polling as the fallback."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.hyperion_apr16.const import FULL_REFRESH_INTERVAL
from custom_components.hyperion_apr16.coordinator import HyperionDataUpdateCoordinator

STATUS = {
    "power": True,
    "volume": 30.0,
    "mute": False,
    "active_input": "HDMI 1",
    "input_id": 1,
    "audio_mode": "multich",
}


def make_device() -> MagicMock:
    device = MagicMock()
    device.host = "192.168.1.50"
    device.async_get_status = AsyncMock(side_effect=lambda: dict(STATUS))
    device.async_get_trim = AsyncMock(return_value={"level": 0})
    device.async_get_gain = AsyncMock(return_value={"level": 0})
    device.async_get_lipsync = AsyncMock(return_value={"delayMs": 0})
    device.async_get_dirac_active_slot = AsyncMock(return_value=1)
    device.async_get_dirac_filtering = AsyncMock(return_value=True)
    device.async_get_input_names = AsyncMock(return_value={1: "Apple TV", 2: "PS5"})
    device.async_get_max_volume = AsyncMock(return_value=75.0)
    device.async_get_power_on_volume = AsyncMock(return_value=35.0)
    device.async_get_version = AsyncMock(return_value={"version": "1.2.0"})
    device.async_get_macaddress = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
    return device


@pytest.fixture
async def coordinator(hass: HomeAssistant) -> AsyncGenerator[HyperionDataUpdateCoordinator]:
    coordinator = HyperionDataUpdateCoordinator(hass, device=make_device())
    await coordinator.async_refresh()
    yield coordinator
    await coordinator.async_shutdown()  # cancels the refresh debounce timer


def pretend_streams_are_live(coordinator: HyperionDataUpdateCoordinator, live: bool = True) -> None:
    coordinator._streams = [SimpleNamespace(live=live)]


# --------------------------------------------------------------------------- polling


async def test_the_status_is_read_over_rest_when_there_are_no_streams(coordinator) -> None:
    await coordinator.async_refresh()

    assert coordinator.device.async_get_status.await_count == 2
    assert coordinator.data["volume"] == 30.0
    assert coordinator.data["mac_address"] == "aa:bb:cc:dd:ee:ff"


async def test_firmware_and_mac_are_only_read_once(coordinator) -> None:
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert coordinator.device.async_get_version.await_count == 1
    assert coordinator.device.async_get_macaddress.await_count == 1
    assert coordinator.data["firmware_version"] == "1.2.0"


async def test_a_mac_address_that_could_not_be_read_is_asked_for_again(hass: HomeAssistant) -> None:
    device = make_device()
    device.async_get_macaddress = AsyncMock(side_effect=[OSError("busy"), "aa:bb:cc:dd:ee:ff"])
    coordinator = HyperionDataUpdateCoordinator(hass, device=device)

    await coordinator.async_refresh()
    assert coordinator.data["mac_address"] == "00:00:00:00:00:00"

    await coordinator.async_refresh()
    assert coordinator.data["mac_address"] == "aa:bb:cc:dd:ee:ff"


async def test_a_failing_processor_makes_the_update_fail(coordinator) -> None:
    coordinator.device.async_get_status.side_effect = OSError("down")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# --------------------------------------------------------------------------- while the streams are live


async def test_nothing_is_polled_while_the_streams_are_live(coordinator) -> None:
    pretend_streams_are_live(coordinator)
    reads = coordinator.device.async_get_status.await_count

    await coordinator._async_update_data()

    assert coordinator.device.async_get_status.await_count == reads


async def test_the_status_is_still_read_now_and_then_as_a_safety_net(coordinator) -> None:
    pretend_streams_are_live(coordinator)
    reads = coordinator.device.async_get_status.await_count
    coordinator._last_full_refresh -= FULL_REFRESH_INTERVAL + 1

    await coordinator._async_update_data()

    assert coordinator.device.async_get_status.await_count == reads + 1


async def test_polling_resumes_when_a_stream_is_lost(coordinator) -> None:
    pretend_streams_are_live(coordinator, live=False)
    reads = coordinator.device.async_get_status.await_count

    await coordinator._async_update_data()

    assert coordinator.device.async_get_status.await_count == reads + 1


async def test_a_command_is_followed_by_a_real_read_even_when_streams_are_live(coordinator) -> None:
    pretend_streams_are_live(coordinator)
    reads = coordinator.device.async_get_status.await_count

    await coordinator.async_request_refresh()
    await coordinator.hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.device.async_get_status.await_count == reads + 1


# --------------------------------------------------------------------------- what the streams say


async def test_volume_mute_and_power_from_the_audio_stream_are_applied_without_a_read(coordinator) -> None:
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_audio_state({"power": False, "volume": 42, "mute": True, "audio_mode": "native"})

    assert coordinator.data["volume"] == 42.0
    assert coordinator.data["volume_db"] is not None
    assert coordinator.data["mute"] is True
    assert coordinator.data["power"] is False
    assert coordinator.device.async_get_status.await_count == reads


async def test_the_volume_limits_are_read_with_the_status(coordinator) -> None:
    assert coordinator.data["max_volume"] == 75.0
    assert coordinator.data["power_on_volume"] == 35.0


async def test_a_volume_limit_that_cannot_be_read_does_not_fail_the_update(hass: HomeAssistant) -> None:
    device = make_device()
    device.async_get_max_volume = AsyncMock(side_effect=OSError("no such endpoint"))
    coordinator = HyperionDataUpdateCoordinator(hass, device=device)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert "max_volume" not in coordinator.data
    assert coordinator.data["power_on_volume"] == 35.0


async def test_the_volume_limits_reported_by_the_audio_stream_are_applied(coordinator) -> None:
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_audio_state({"volume": 30, "max_volume": 60, "on_volume": 25})

    assert coordinator.data["max_volume"] == 60.0
    assert coordinator.data["power_on_volume"] == 25.0
    assert coordinator.device.async_get_status.await_count == reads


async def test_the_dirac_slot_and_input_names_are_read_with_the_status(coordinator) -> None:
    assert coordinator.data["active_slot"] == 1
    assert coordinator.data["input_names"] == {1: "Apple TV", 2: "PS5"}


async def test_dirac_filtering_is_read_from_the_processor(coordinator) -> None:
    assert coordinator.data["dirac_active"] is True


async def test_dirac_filtering_keeps_its_last_value_when_it_cannot_be_read(coordinator) -> None:
    coordinator.device.async_get_dirac_filtering.return_value = None

    await coordinator.async_refresh()

    assert coordinator.data["dirac_active"] is True


async def test_dirac_filtering_is_unknown_until_it_has_been_read(hass: HomeAssistant) -> None:
    device = make_device()
    device.async_get_dirac_filtering = AsyncMock(return_value=None)
    coordinator = HyperionDataUpdateCoordinator(hass, device=device)

    await coordinator.async_refresh()

    assert coordinator.data["dirac_active"] is None


async def test_dirac_filtering_from_the_stream_is_applied_without_a_read(coordinator) -> None:
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_dirac_state({"active_slot": 1, "filtering_enabled": False})

    assert coordinator.data["dirac_active"] is False
    assert coordinator.device.async_get_status.await_count == reads


async def test_a_change_of_dirac_slot_from_the_stream_is_applied_without_a_read(coordinator) -> None:
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_dirac_state({"active_slot": 2, "filtering_enabled": True})

    assert coordinator.data["active_slot"] == 2
    assert coordinator.device.async_get_status.await_count == reads


async def test_dirac_states_without_a_usable_slot_are_ignored(coordinator) -> None:
    before = dict(coordinator.data)

    coordinator._on_dirac_state({"active_slot": "two"})
    coordinator._on_dirac_state({"filtering_enabled": True})

    assert coordinator.data == before


async def test_loudness_comes_from_the_speakers_stream(coordinator) -> None:
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_speakers_state({"loudness_capability": "supported", "loudness_enabled": True, "layout": "7.3.6"})

    assert coordinator.data["loudness"] is True
    assert coordinator.data["loudness_supported"] is True
    assert coordinator.device.async_get_status.await_count == reads


async def test_loudness_is_not_supported_when_the_processor_says_so(coordinator) -> None:
    coordinator._on_speakers_state({"loudness_capability": "unsupported", "loudness_enabled": False})

    assert coordinator.data["loudness_supported"] is False


async def test_loudness_survives_a_refresh_over_rest(coordinator) -> None:
    coordinator._on_speakers_state({"loudness_capability": "supported", "loudness_enabled": True})

    await coordinator.async_refresh()  # REST knows nothing about loudness

    assert coordinator.data["loudness"] is True
    assert coordinator.data["loudness_supported"] is True


async def test_loudness_is_unknown_until_the_processor_has_reported_it(coordinator) -> None:
    assert "loudness" not in coordinator.data
    assert "loudness_supported" not in coordinator.data


async def test_speaker_states_without_loudness_are_ignored(coordinator) -> None:
    before = dict(coordinator.data)

    coordinator._on_speakers_state({"layout": "7.3.6", "loudness_enabled": "yes", "loudness_capability": 1})

    assert coordinator.data == before


async def test_values_of_the_wrong_type_are_ignored(coordinator) -> None:
    before = dict(coordinator.data)

    coordinator._on_audio_state({"power": "yes", "volume": "loud", "mute": 1})

    assert coordinator.data == before


async def test_a_change_of_audio_format_makes_the_status_be_read_again(coordinator) -> None:
    coordinator._on_audio_state({"volume": 30, "audio_format": "PCM 2.0ch"})  # the first state is the baseline
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_audio_state({"volume": 30, "audio_format": "Neural:X"})
    await coordinator.hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.device.async_get_status.await_count == reads + 1


async def test_a_change_of_volume_alone_does_not_make_the_status_be_read_again(coordinator) -> None:
    coordinator._on_audio_state({"volume": 30, "audio_format": "PCM 2.0ch"})
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_audio_state({"volume": 31, "audio_format": "PCM 2.0ch"})
    await coordinator.hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.device.async_get_status.await_count == reads


async def test_a_change_of_input_makes_the_status_be_read_again(coordinator) -> None:
    coordinator._on_inputs_state({"active_input": 1})  # the first state is the baseline
    reads = coordinator.device.async_get_status.await_count

    coordinator._on_inputs_state({"active_input": 2})
    await coordinator.hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.device.async_get_status.await_count == reads + 1


# --------------------------------------------------------------------------- starting and stopping


async def test_the_streams_are_started_and_stopped(coordinator) -> None:
    async def never_connects():
        raise OSError("no processor here")

    coordinator.device.async_open_state_stream = never_connects

    coordinator.async_start_streams()
    assert len(coordinator._streams) == 4
    assert not coordinator.streams_live

    await coordinator.async_stop_streams()
    assert coordinator._streams == []
