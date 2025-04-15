"""Binary sensor platform for ChirpStack HTTP integration."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

class ChirpstackBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a ChirpStack binary sensor."""
    
    def __init__(self, device_id, name, unique_id, device_info):
        """Initialize the binary sensor."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        
        # Create device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_info.get("deviceName", f"Device {device_id}"),
            manufacturer=device_info.get("tenantName", "ChirpStack"),
            model=device_info.get("deviceProfileName", "Unknown")
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
        if hasattr(self, 'hass') and self.hass is not None:
            _LOGGER.debug(f"Writing state for binary sensor {self.name}")
            self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform."""
    entry_id = entry.entry_id
    _LOGGER.debug(f"Setting up ChirpStack binary sensor platform for entry {entry_id}")
    
    # Store the add_entities function
    hass.data[DOMAIN][entry_id]["_platform_binary_sensor"] = async_add_entities
    
    # Add any pending sensors
    if hass.data[DOMAIN][entry_id].get("pending_binary_sensors", []):
        _LOGGER.debug(f"Adding {len(hass.data[DOMAIN][entry_id]['pending_binary_sensors'])} pending sensors")
        async_add_entities(hass.data[DOMAIN][entry_id]["pending_binary_sensors"])
        hass.data[DOMAIN][entry_id]["pending_binary_sensors"] = []