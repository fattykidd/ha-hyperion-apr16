"""Test the AudioControl Hyperion APR-16 integration setup and coordinator."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hyperion_apr16.const import DOMAIN


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Test successful setup and unload of the integration."""
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

    # Mock out the device client connection and data fetches
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
        patch("custom_components.hyperion_apr16.Apr16") as mock_client_class,
    ):
        # Configure mock client instance methods
        mock_client = mock_client_class.return_value
        mock_client.async_connect = AsyncMock(return_value=True)

        # Set up the config entry
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entry loaded successfully
        assert config_entry.state == ConfigEntryState.LOADED

        # Test unloading the entry
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED
