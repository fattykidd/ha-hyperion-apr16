"""Test the AudioControl Hyperion APR-16 media player entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN


async def test_media_player_entity(hass: HomeAssistant) -> None:
    """Test media player entity state and service commands."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "address": "192.168.1.50",
            "port": 50000,
            "name": "Hyperion APR-16",
        },
        entry_id="test_entry_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.hyperion_apr16.coordinator.HyperionDataUpdateCoordinator._async_update_data",
            return_value={
                "power": True,
                "volume": -20.0,
                "mute": False,
                "active_input": "HDMI 1",
                "audio_mode": "Auto",
                "brightness": 80,
            },
        ),
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class
    ):
        mock_client = mock_client_class.return_value
        mock_client.async_connect = AsyncMock(return_value=True)
        mock_client.async_send_command = AsyncMock(return_value=True)
        mock_client.power_off = AsyncMock(return_value=True)
        mock_client.async_power_off = AsyncMock(return_value=True)
        mock_client.power_on = AsyncMock(return_value=True)
        mock_client.async_power_on = AsyncMock(return_value=True)

        # Set up the integration entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Dynamically grab the registered media player entity ID
        entity_ids = hass.states.async_entity_ids("media_player")
        assert len(entity_ids) > 0
        entity_id = entity_ids[0]

        # Verify the media player entity state loaded properly
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == MediaPlayerState.ON

        # Test sending a turn_off service call
        await hass.services.async_call(
            "media_player",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

        # Ensure the device client power off method was called
        assert mock_client.power_off.called or mock_client.async_power_off.called
