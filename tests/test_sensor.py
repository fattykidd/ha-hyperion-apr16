"""The video sensors."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN

ENTRY_ID = "test_entry_id"

STATUS = {
    "power": True,
    "video_detail": "Chroma: 422 | Colorimetry: BT709 | Bit Depth: 8bit",
    "video_format": "3840x2160@59.94p",
    "hdr_status": "SDR",
}


@pytest.fixture
async def integration(hass: HomeAssistant):
    """The integration set up against a fake processor that reports a 4K SDR signal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "192.168.1.50", "port": 8080, "name": "Hyperion APR-16"},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator._async_update_data",
            return_value=dict(STATUS),
        ),
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class,
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator.async_start_streams"
        ),
    ):
        mock_client_class.return_value.async_get_dirac_filter_slots_list.return_value = []
        assert await hass.config_entries.async_setup(ENTRY_ID)
        await hass.async_block_till_done()
        yield entry

        await hass.config_entries.async_unload(ENTRY_ID)


def state_of(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{ENTRY_ID}_{key}")
    assert entity_id, f"no sensor for {key}"
    return hass.states.get(entity_id).state


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("video_detail", "Chroma: 422 | Colorimetry: BT709 | Bit Depth: 8bit"),
        ("video_format", "3840x2160@59.94p"),
        ("hdr_status", "SDR"),
    ],
)
async def test_the_video_sensors_show_what_the_processor_reports(hass: HomeAssistant, integration, key, expected) -> None:
    assert state_of(hass, key) == expected


async def test_the_video_sensors_follow_the_signal(hass: HomeAssistant, integration) -> None:
    coordinator = hass.data[DOMAIN][ENTRY_ID]["coordinator"]

    coordinator._on_video_state({"video_format": "No Signal", "video_detail": "Chroma: RGB", "hdr_status": "SDR"})
    await hass.async_block_till_done()

    assert state_of(hass, "video_format") == "No Signal"
    assert state_of(hass, "video_detail") == "Chroma: RGB"
