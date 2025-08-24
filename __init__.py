from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
import logging
import json
from .http import ChirpstackHttpView

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.device_states"
SAVE_INTERVAL = timedelta(minutes=15)  # How often to save state


async def async_setup(hass, config):
    """Set up the ChirpStack HTTP component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    entry_id = config_entry.entry_id
    hass.data.setdefault(DOMAIN, {})
    # Set up storage for device states
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_states = await store.async_load() or {}

    hass.data[DOMAIN][entry_id] = {
        "sensors": [],
        "binary_sensors": [],
        "devices": stored_states.get(entry_id, {}),
        "pending_sensors": [],
        "pending_binary_sensors": [],
        "store": store,
    }

    # Set up periodic saving of device states
    async def _save_states(_now=None):
        all_states = await store.async_load() or {}
        all_states[entry_id] = hass.data[DOMAIN][entry_id]["devices"]
        await store.async_save(all_states)

    hass.data[DOMAIN][entry_id]["cancel_save_interval"] = async_track_time_interval(
        hass, _save_states, SAVE_INTERVAL
    )

    # Register the view
    url_suffix = config_entry.data["url_suffix"]
    header_name = config_entry.data.get("header_name")
    header_value = config_entry.data.get("header_value")
    hass.http.register_view(
        ChirpstackHttpView(hass, entry_id, url_suffix, header_name, header_value)
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
