"""Binary sensor platform for the ChirpStack HTTP integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    PENDING_BINARY_SENSORS_KEY,
    ADD_BINARY_SENSOR_ENTITIES_FUNC_KEY,
    CS_DEVICE_NAME_KEY,
    CS_TENANT_NAME_KEY,
    CS_TENANT_NAME_DEFAULT,
    CS_DEVICE_PROFILE_NAME_KEY,
    CS_DEVICE_PROFILE_NAME_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


class ChirpstackBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a ChirpStack binary sensor."""

    def __init__(
        self,
        name: str,
        unique_id: str,
        device_id: str,
        device_class: BinarySensorDeviceClass,
        device_info: dict[str, str],
    ):
        """Initialize the binary sensor."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        if device_class:
            self._attr_device_class = device_class

        # Create device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_info.get(CS_DEVICE_NAME_KEY, f"Device {device_id}"),
            manufacturer=device_info.get(CS_TENANT_NAME_KEY, CS_TENANT_NAME_DEFAULT),
            model=device_info.get(
                CS_DEVICE_PROFILE_NAME_KEY, CS_DEVICE_PROFILE_NAME_DEFAULT
            ),
        )

        _LOGGER.debug(f"Created binary sensor: {name}")

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore the last known state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug(f"Restored state for {self.name}: {last_state.state}")
        else:
            _LOGGER.debug(f"No previous state found for {self.name}")

    def set_initial_value(self, value):
        """Set the value without triggering a state update"""
        _LOGGER.debug(f"Setting initial value for {self.name}: {value}")
        self._attr_native_value = value
        self._pending_value = None

    def update_state(self, value):
        """Update the binary sensor state."""
        _LOGGER.debug(f"Updating binary sensor '{self.name}' with value: {value}")

        # Store the state
        self._attr_is_on = value

        # If already added to HA, write state
        if hasattr(self, "hass") and self.hass is not None:
            _LOGGER.debug(f"Writing state for binary sensor {self.name}")
            self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
):
    """Set up the binary sensor platform."""
    entry_id = entry.entry_id
    _LOGGER.debug(f"Setting up ChirpStack binary sensor platform for entry {entry_id}")

    # Store the add_entities function
    hass.data[DOMAIN][entry_id][ADD_BINARY_SENSOR_ENTITIES_KEY] = async_add_entities

    # Add any pending sensors
    pending_sensors = hass.data[DOMAIN][entry_id].get(PENDING_BINARY_SENSORS_KEY, [])
    if pending_sensors:
        _LOGGER.debug(f"Adding {len(pending_sensors)} pending sensors")
        async_add_entities(pending_sensors)
        hass.data[DOMAIN][entry_id][PENDING_BINARY_SENSORS_KEY] = []
