from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval

from .http import ChirpstackHttpView
from .const import (
    DOMAIN,
    SENSORS_KEY,
    BINARY_SENSORS_KEY,
    DEVICES_KEY,
    PENDING_SENSORS_KEY,
    PENDING_BINARY_SENSORS_KEY,
    STORE_KEY,
    STORAGE_KEY,
    API_URL_SUFFIX_KEY,
    API_HEADER_NAME_KEY,
    API_HEADER_VALUE_KEY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
STORAGE_VERSION = 1
SAVE_INTERVAL = timedelta(minutes=15)  # How often to save state

# https://developers.home-assistant.io/docs/config_entries_index/


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
        SENSORS_KEY: [],
        BINARY_SENSORS_KEY: [],
        DEVICES_KEY: stored_states.get(entry_id, {}),
        PENDING_SENSORS_KEY: [],
        PENDING_BINARY_SENSORS_KEY: [],
        STORE_KEY: store,
    }

    # Set up periodic saving of device states
    async def _save_states(_now=None):
        all_states = await store.async_load() or {}
        all_states[entry_id] = hass.data[DOMAIN][entry_id][DEVICES_KEY]
        await store.async_save(all_states)

    hass.data[DOMAIN][entry_id]["cancel_save_interval"] = async_track_time_interval(
        hass, _save_states, SAVE_INTERVAL
    )

    # Register the view
    url_suffix = config_entry.data[API_URL_SUFFIX_KEY]
    header_name = config_entry.data.get(API_HEADER_NAME_KEY)
    header_value = config_entry.data.get(API_HEADER_VALUE_KEY)
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
