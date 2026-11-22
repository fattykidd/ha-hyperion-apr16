"""The Dirac Active switch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN

ENTRY_ID = "test_entry_id"


async def setup_integration(hass: HomeAssistant, processor: dict):
    """
    Set the integration up against a fake processor.

    ``processor`` is what the processor currently reports. Setting Dirac filtering changes it, so a refresh
    after a command reads the new state, as it would from a real processor.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "192.168.1.50", "port": 8080, "name": "Hyperion APR-16"},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator._async_update_data",
            side_effect=lambda: {"power": True, **processor},
        ),
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class,
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator.async_start_streams"
        ),
    ):
        device = mock_client_class.return_value
        device.async_get_dirac_filter_slots_list = AsyncMock(return_value=[])  # asked by the button platform
        device.async_set_dirac_filtering = AsyncMock(
            side_effect=lambda enabled: processor.update(dirac_active=enabled)
        )

        assert await hass.config_entries.async_setup(ENTRY_ID)
        await hass.async_block_till_done()
        yield device

        await hass.config_entries.async_unload(ENTRY_ID)


@pytest.fixture
async def device(hass: HomeAssistant):
    async for device in setup_integration(hass, {"dirac_active": False}):
        yield device


@pytest.fixture
async def device_unknown(hass: HomeAssistant):
    async for device in setup_integration(hass, {"dirac_active": None}):
        yield device


def switch_id(hass: HomeAssistant) -> str:
    found = er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{ENTRY_ID}_dirac_switch")
    assert found
    return found


async def test_the_switch_shows_what_the_processor_reports(hass: HomeAssistant, device) -> None:
    assert hass.states.get(switch_id(hass)).state == "off"


async def test_the_switch_is_unknown_until_the_processor_has_reported(hass: HomeAssistant, device_unknown) -> None:
    assert hass.states.get(switch_id(hass)).state == "unknown"


async def test_turning_it_on_tells_the_processor(hass: HomeAssistant, device) -> None:
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id(hass)}, blocking=True)

    device.async_set_dirac_filtering.assert_awaited_once_with(True)
    assert hass.states.get(switch_id(hass)).state == "on"


async def test_turning_it_off_tells_the_processor(hass: HomeAssistant, device) -> None:
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_id(hass)}, blocking=True)

    device.async_set_dirac_filtering.assert_awaited_once_with(False)
