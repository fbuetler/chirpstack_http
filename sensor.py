"""Sensor platform for the ChirpStack HTTP integration."""

import re
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    PENDING_SENSORS_KEY,
    ADD_SENSOR_ENTITIES_FUNC_KEY,
    CS_DEVICE_NAME_KEY,
    CS_TENANT_NAME_KEY,
    CS_TENANT_NAME_DEFAULT,
    CS_DEVICE_PROFILE_NAME_KEY,
    CS_DEVICE_PROFILE_NAME_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
):
    """Set up the sensor platform."""
    entry_id = entry.entry_id
    _LOGGER.debug(f"Setting up ChirpStack sensor platform for entry {entry_id}")

    # Store the add_entities function
    hass.data[DOMAIN][entry_id][ADD_SENSOR_ENTITIES_FUNC_KEY] = async_add_entities

    # Add any pending sensors
    pending_sensors = hass.data[DOMAIN][entry_id].get(PENDING_SENSORS_KEY, [])
    if pending_sensors:
        _LOGGER.debug(f"Adding {len(pending_sensors)} pending sensors")
        async_add_entities(pending_sensors)
        hass.data[DOMAIN][entry_id][PENDING_SENSORS_KEY] = []


class ChirpstackSensor(SensorEntity, RestoreEntity):
    """Representation of a ChirpStack sensor."""

    def __init__(
        self,
        device_id: str,
        unique_id: str,
        name: str,
        device_class: SensorDeviceClass,
        device_info: dict[str, str],
        unit: str,
    ):
        """Initialize the sensor."""
        self._device_id = device_id

        # common entity properties
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_info.get(CS_DEVICE_NAME_KEY, f"Device {device_id}"),
            manufacturer=device_info.get(CS_TENANT_NAME_KEY, CS_TENANT_NAME_DEFAULT),
            model=device_info.get(
                CS_DEVICE_PROFILE_NAME_KEY, CS_DEVICE_PROFILE_NAME_DEFAULT
            ),
        )

        # sensor entity property
        self._attr_native_unit_of_measurement = unit

        _LOGGER.debug(f"Created sensor: {name} with unit {unit}")

    # https://developers.home-assistant.io/docs/core/entity/#async_added_to_hass
    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

    def set_initial_state(self, state: StateType):
        """Set the state without triggering a state update"""
        _LOGGER.debug(
            f"Setting initial state for {self.name}: {state} {self._attr_native_unit_of_measurement}"
        )

        state = self.sanitize_state(state)
        self._attr_native_value = state  # sensor entity property

    def update_state(self, state: StateType):
        """Update the sensor state."""
        _LOGGER.debug(
            f"Updating sensor '{self.name}' with state: {state} ({type(state).__name__})"
        )

        state = self.sanitize_state(state)
        self._attr_native_value = state  # sensor entity property
        self.async_write_ha_state()

    def sanitize_state(self, state: StateType):
        """Sanitize the state based on its type."""
        if isinstance(state, str):
            # Attempt to convert to float if it's a numeric string
            if re.match(r"^\d+(\.\d+)?$", state):
                return float(state)
        return state
