"""The level meter entities: a switch, 16 level sensors, 16 peak sensors and a reset button."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN

from .meter_fakes import FakeStream, quiet, wait_until

ENTRY_ID = "test_entry_id"


@pytest.fixture
async def stream(hass: HomeAssistant):
    """The integration set up against a fake processor whose level meters are this stream."""
    stream = FakeStream()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "192.168.1.50", "port": 8080, "name": "Hyperion APR-16"},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator._async_update_data",
            side_effect=lambda: {"power": True},
        ),
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class,
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator.async_start_streams"
        ),
    ):
        device = mock_client_class.return_value
        device.async_get_dirac_filter_slots_list = AsyncMock(return_value=[])
        device.async_open_meter_stream = stream

        assert await hass.config_entries.async_setup(ENTRY_ID)
        await hass.async_block_till_done()
        yield stream

        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(ENTRY_ID)


def entity_id(hass: HomeAssistant, domain: str, key: str) -> str:
    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ENTRY_ID}_{key}")
    assert found, key
    return found


def state_of(hass: HomeAssistant, domain: str, key: str) -> str:
    return hass.states.get(entity_id(hass, domain, key)).state


async def switch_meters(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        "switch", service, {"entity_id": entity_id(hass, "switch", "level_meters")}, blocking=True
    )


async def test_the_meters_are_off_and_nothing_is_requested_until_asked(hass: HomeAssistant, stream) -> None:
    assert state_of(hass, "switch", "level_meters") == "off"
    assert state_of(hass, "sensor", "level_1") == "unknown"
    assert stream.opened == 0


async def test_there_is_a_level_and_a_peak_sensor_for_each_of_the_sixteen_outputs(
    hass: HomeAssistant, stream
) -> None:
    for output in range(1, 17):
        assert entity_id(hass, "sensor", f"level_{output}")
        assert entity_id(hass, "sensor", f"peak_{output}")
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{ENTRY_ID}_level_17") is None


async def test_switching_on_shows_the_levels_in_db(hass: HomeAssistant, stream) -> None:
    await switch_meters(hass, "turn_on")
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-18, ch16=-40))
    await wait_until(lambda: state_of(hass, "sensor", "level_1") == "-18")

    assert state_of(hass, "switch", "level_meters") == "on"
    assert state_of(hass, "sensor", "level_16") == "-40"
    assert state_of(hass, "sensor", "level_2") == "-96"
    assert state_of(hass, "sensor", "peak_1") == "-18"
    assert hass.states.get(entity_id(hass, "sensor", "level_1")).attributes["unit_of_measurement"] == "dB"


async def test_switching_off_clears_the_levels_but_the_peaks_stay(hass: HomeAssistant, stream) -> None:
    await switch_meters(hass, "turn_on")
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-18))
    await wait_until(lambda: state_of(hass, "sensor", "level_1") == "-18")

    await switch_meters(hass, "turn_off")

    assert state_of(hass, "switch", "level_meters") == "off"
    assert state_of(hass, "sensor", "level_1") == "unknown"
    assert state_of(hass, "sensor", "peak_1") == "-18"
    assert stream.closed == 1


async def test_reset_peaks_clears_the_held_peaks(hass: HomeAssistant, stream) -> None:
    await switch_meters(hass, "turn_on")
    await wait_until(lambda: stream.opened)
    stream.send(quiet(ch1=-18))
    await wait_until(lambda: state_of(hass, "sensor", "peak_1") == "-18")

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", "reset_peaks")}, blocking=True
    )

    assert state_of(hass, "sensor", "peak_1") == "unknown"
    stream.send(quiet(ch1=-60))
    await wait_until(lambda: state_of(hass, "sensor", "peak_1") == "-60")


async def test_unloading_the_integration_stops_the_meters(hass: HomeAssistant, stream) -> None:
    await switch_meters(hass, "turn_on")
    await wait_until(lambda: stream.opened)

    assert await hass.config_entries.async_unload(ENTRY_ID)
    await hass.async_block_till_done()

    assert stream.closed == 1


def friendly_name(hass: HomeAssistant, domain: str, key: str) -> str:
    return hass.states.get(entity_id(hass, domain, key)).attributes["friendly_name"]


async def test_the_sensors_are_named_after_the_speaker_on_each_output(hass: HomeAssistant, stream) -> None:
    coordinator = hass.data[DOMAIN][ENTRY_ID]["coordinator"]

    coordinator.async_set_updated_data({**coordinator.data, "output_names": {1: "Front Left", 4: "Sub 1"}})
    await hass.async_block_till_done()

    assert friendly_name(hass, "sensor", "level_1").endswith(" Level Front Left")
    assert friendly_name(hass, "sensor", "peak_4").endswith(" Peak Sub 1")
    assert friendly_name(hass, "sensor", "level_2").endswith(" Level Output 2")  # nothing reported for it
    assert entity_id(hass, "sensor", "level_1").endswith("level_output_1")  # the entity id stays put


async def test_the_sensors_follow_a_change_of_speaker_layout(hass: HomeAssistant, stream) -> None:
    coordinator = hass.data[DOMAIN][ENTRY_ID]["coordinator"]
    coordinator.async_set_updated_data({**coordinator.data, "output_names": {1: "Front Left"}})
    await hass.async_block_till_done()

    coordinator.async_set_updated_data({**coordinator.data, "output_names": {1: "Left Wide"}})
    await hass.async_block_till_done()

    assert friendly_name(hass, "sensor", "level_1").endswith(" Level Left Wide")
