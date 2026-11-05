"""Test the AudioControl Hyperion APR-16 config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hyperion_apr16.const import DOMAIN


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the user config form and successfully create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.hyperion_apr16.config_flow.Apr16"
        ) as mock_client_class,
        patch(
            "custom_components.hyperion_apr16.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        mock_client = mock_client_class.return_value
        mock_client.async_connect = AsyncMock(return_value=True)
        mock_client.async_get_macaddress = AsyncMock(return_value="00:11:22:33:44:55")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: "192.168.1.50",
                CONF_PORT: 50000,
                CONF_NAME: "Hyperion APR-16",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Hyperion APR-16"
        assert result2["data"] == {
            CONF_ADDRESS: "192.168.1.50",
            CONF_PORT: 50000,
            CONF_NAME: "Hyperion APR-16",
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test handling connection errors during config flow validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.hyperion_apr16.config_flow.Apr16"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.async_connect = AsyncMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: "192.168.1.50",
                CONF_PORT: 50000,
                CONF_NAME: "Hyperion APR-16",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}