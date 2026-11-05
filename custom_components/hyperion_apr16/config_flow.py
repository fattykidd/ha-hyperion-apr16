"""Config flow for AudioControl Hyperion APR-16."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config import APR16Config
from .const import DEFAULT_PORT, DOMAIN
from .device import Apr16

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME, default="Hyperion APR-16"): str,
    }
)


class HyperionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AudioControl Hyperion APR-16."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            config = APR16Config(
                identifier="temp",
                name=user_input.get(CONF_NAME, "Hyperion APR-16"),
                address=user_input[CONF_ADDRESS],
                port=user_input[CONF_PORT],
            )
            device = Apr16(device_config=config, session=session)

            try:
                await device.async_connect()
            except (TimeoutError, aiohttp.ClientError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # If connection succeeds, create the config entry
                return self.async_create_entry(
                    title=user_input.get("name", "AudioControl APR-16"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )