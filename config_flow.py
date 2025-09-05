from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    DOMAIN,
    API_URL_PREFIX,
    API_URL_SUFFIX_KEY,
    API_URL_SUFFIX_DEFAULT,
    API_HEADER_NAME_KEY,
    API_HEADER_VALUE_KEY,
)


# https://developers.home-assistant.io/docs/config_entries_config_flow_handler/
class ChirpstackHttpConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    # default step
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}

        if user_input is not None:
            url_suffix = user_input.get(API_URL_SUFFIX_KEY, API_URL_SUFFIX_DEFAULT)
            header_name = user_input.get(API_HEADER_NAME_KEY, "")
            header_value = user_input.get(API_HEADER_VALUE_KEY, "")

            # Create entry with user input data
            return self.async_create_entry(
                title=f"{API_URL_PREFIX}/{url_suffix}",
                data={
                    API_URL_SUFFIX_KEY: url_suffix,
                    API_HEADER_NAME_KEY: header_name,
                    API_HEADER_VALUE_KEY: header_value,
                },
            )

        # Show configuration form
        schema = vol.Schema(
            {
                vol.Required("url_suffix", default="chirpstack"): str,
                vol.Optional(
                    "header_name", description="Optional authentication header name"
                ): str,
                vol.Optional(
                    "header_value", description="Optional authentication header value"
                ): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
