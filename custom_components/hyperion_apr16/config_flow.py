"""Config flow for AudioControl Hyperion APR-16 integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from device import Apr16
from config import APR16Config

_LOG = logging.getLogger(__name__)


class HyperionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AudioControl Hyperion APR-16."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            name = user_input.get(CONF_NAME, DEFAULT_NAME)

            # Test connection using a temporary Apr16 client instance
            device_config = APR16Config(
                identifier="temp_config",
                name=name,
                address=address,
                port=port,
            )
            device = Apr16(device_config=device_config, loop=None)

            try:
                await device.verify_connection()
            except Exception as err:
                _LOG.error("Failed to connect to Hyperion at %s:%s: %s", address, port, err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_PORT: port,
                        CONF_NAME: name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )