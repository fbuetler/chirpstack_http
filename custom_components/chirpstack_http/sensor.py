"""Sensor platform for the ChirpStack HTTP integration."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
import re
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"


# Simplified sensor class
class ChirpstackSensor(SensorEntity, RestoreEntity):
    """Representation of a ChirpStack sensor."""

    def __init__(self, device_id, name, device_class, unit, unique_id, device_info):
        """Initialize the sensor."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class

        # Create device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_info.get("deviceName", f"Device {device_id}"),
            manufacturer=device_info.get("tenantName", "ChirpStack"),
            model=device_info.get("deviceProfileName", "Unknown"),
        )

        # Debug logging
        _LOGGER.debug(f"Created sensor: {name} with unit {unit}")

    def set_initial_value(self, value):
        """Set the value without triggering a state update"""
        _LOGGER.debug(
            f"Setting initial value for {self.name}: {value} {self._attr_native_unit_of_measurement}"
        )

        value = self.sanitize_value(value)
        self._attr_native_value = value
        self._pending_value = None

    def sanitize_value(self, value):
        """Sanitize the value based on its type."""
        if isinstance(value, str):
            # Attempt to convert to float if it's a numeric string
            if re.match(r"^\d+(\.\d+)?$", value):
                return float(value)
        return value

    def update_state(self, value):
        """Update the sensor state."""
        _LOGGER.debug(
            f"Updating sensor '{self.name}' with value: {value} ({type(value).__name__})"
        )

        # Sanitize the value
        value = self.sanitize_value(value)

        # Store the raw value
        self._attr_native_value = value

        # If already added to HA, write state
        if hasattr(self, "hass") and self.hass is not None:
            _LOGGER.debug(f"Writing state for {self.name}")
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    entry_id = entry.entry_id
    _LOGGER.debug(f"Setting up ChirpStack binary sensor platform for entry {entry_id}")

    # Store the add_entities function
    hass.data[DOMAIN][entry_id]["_platform_sensor"] = async_add_entities

    # Add any pending sensors
    if hass.data[DOMAIN][entry_id].get("pending_sensors", []):
        _LOGGER.debug(
            f"Adding {len(hass.data[DOMAIN][entry_id]['pending_sensors'])} pending sensors"
        )
        async_add_entities(hass.data[DOMAIN][entry_id]["pending_sensors"])
        hass.data[DOMAIN][entry_id]["pending_sensors"] = []
