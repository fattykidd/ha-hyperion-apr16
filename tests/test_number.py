"""The volume limit sliders."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN

ENTRY_ID = "test_entry_id"


@pytest.fixture
async def device(hass: HomeAssistant):
    """The integration set up against a fake device that reports its volume limits."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": "192.168.1.50", "port": 8080, "name": "Hyperion APR-16"},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator._async_update_data",
            return_value={"power": True, "volume": 30.0, "max_volume": 75.0, "power_on_volume": 35.0},
        ),
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class,
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator.async_start_streams"
        ),
    ):
        device = mock_client_class.return_value
        device.async_get_dirac_filter_slots_list = AsyncMock(return_value=[])  # asked by the button platform
        device.set_max_volume = AsyncMock()
        device.set_power_on_volume = AsyncMock()

        assert await hass.config_entries.async_setup(ENTRY_ID)
        await hass.async_block_till_done()
        yield device

        await hass.config_entries.async_unload(ENTRY_ID)


def entity_id(hass: HomeAssistant, key: str) -> str:
    registry = er.async_get(hass)
    found = registry.async_get_entity_id("number", DOMAIN, f"{ENTRY_ID}_{key}")
    assert found, f"no number entity for {key}"
    return found


@pytest.mark.parametrize(("key", "value"), [("max_volume", "75.0"), ("power_on_volume", "35.0")])
async def test_the_limits_show_what_the_processor_reports(hass: HomeAssistant, device, key, value) -> None:
    assert hass.states.get(entity_id(hass, key)).state == value


async def test_the_limits_are_settings_not_dashboard_controls(hass: HomeAssistant, device) -> None:
    registry = er.async_get(hass)

    for key in ("max_volume", "power_on_volume"):
        assert registry.async_get(entity_id(hass, key)).entity_category == EntityCategory.CONFIG


async def test_setting_the_maximum_volume_tells_the_processor(hass: HomeAssistant, device) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id(hass, "max_volume"), "value": 60}, blocking=True
    )

    device.set_max_volume.assert_awaited_once_with(60)
    device.set_power_on_volume.assert_not_awaited()


async def test_setting_the_power_on_volume_tells_the_processor(hass: HomeAssistant, device) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id(hass, "power_on_volume"), "value": 20}, blocking=True
    )

    device.set_power_on_volume.assert_awaited_once_with(20)
    device.set_max_volume.assert_not_awaited()
