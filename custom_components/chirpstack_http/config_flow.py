from homeassistant import config_entries
import voluptuous as vol

DOMAIN = "chirpstack_http"

class ChirpstackHttpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url_suffix = user_input.get("url_suffix", "chirpstack")
            header_name = user_input.get("header_name", "")
            header_value = user_input.get("header_value", "")

            # Create entry with user input data
            return self.async_create_entry(
                title=f"Webhook: /api/chirpstack_http/{url_suffix}",
                data={
                    "url_suffix": url_suffix,
                    "header_name": header_name,
                    "header_value": header_value
                }
            )

        # Show configuration form
        schema = vol.Schema({
            vol.Required("url_suffix", default="chirpstack"): str,
            vol.Optional("header_name", description="Optional authentication header name"): str,
            vol.Optional("header_value", description="Optional authentication header value"): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)