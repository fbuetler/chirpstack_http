"""HTTP component for ChirpStack integration."""

import logging
import json

from homeassistant.components.http import HomeAssistantView

from .sensor import ChirpstackSensor
from .binary_sensor import ChirpstackBinarySensor
from .helpers import detect_sensor_unit, detect_binary_sensor_device_class
from .const import (
    ADD_BINARY_SENSOR_ENTITIES_KEY,
    ADD_SENSOR_ENTITIES_KEY,
    API_URL_PREFIX,
    CS_DEVICE_EUI_KEY,
    CS_DEVICE_INFO_KEY,
    CS_DEVICE_NAME_KEY,
    CS_DEVICE_PROFILE_NAME_DEFAULT,
    CS_DEVICE_PROFILE_NAME_KEY,
    CS_GATEWAY_ID_DEFAULT,
    CS_GATEWAY_ID_KEY,
    CS_OBJECT_KEY,
    CS_RX_INFO_KEY,
    CS_TENANT_NAME_DEFAULT,
    CS_TENANT_NAME_KEY,
    CS_TYPE_REF_KEY,
    DEVICES_KEY,
    DOMAIN,
    PENDING_BINARY_SENSORS_KEY,
    PENDING_SENSORS_KEY,
)

_LOGGER = logging.getLogger(__name__)


def flatten_dict(d, parent_key="", sep="_"):
    """Flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def sanitize_value(value, key=None):
    """Convert value to proper type and format."""
    if isinstance(value, bool):
        # Already boolean
        return value

    # Check for string booleans
    if isinstance(value, str):
        if value.lower() in ["true", "1", "yes", "y", "on"]:
            return True
        elif value.lower() in ["false", "0", "no", "n", "off"]:
            return False

    # Handle numeric values
    if isinstance(value, (int, float)):
        # Already numeric
        return value

    if isinstance(value, str):
        # Try to convert to number
        try:
            # Try integer first
            if value.isdigit():
                return int(value)
            # Try float next
            return float(value)
        except (ValueError, TypeError):
            # Keep as string
            pass

    # Return as-is for other types
    return value


class ChirpstackHttpView(HomeAssistantView):
    """View to handle ChirpStack webhook requests."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id,
        url_suffix,
        header_name=None,
        header_value=None,
    ):
        """Initialize the webhook view."""
        self.hass = hass
        self.entry_id = entry_id

        # view
        self.url = f"{API_URL_PREFIX}/{url_suffix}"
        self.requires_auth = False

        # custom header
        self.header_name = header_name
        self.header_value = header_value

    async def post(self, request):
        """Handle POST requests for ChirpStack uplinks."""
        try:
            # Check for authentication header if configured
            if self.header_name and self.header_value:
                if self.header_name not in request.headers:
                    _LOGGER.warning(
                        f"Missing authentication header: {self.header_name}"
                    )
                    return self.json(
                        {"status": "error", "message": "Unauthorized"}, status_code=401
                    )

                if request.headers.get(self.header_name) != self.header_value:
                    _LOGGER.warning(
                        f"Invalid authentication header value for: {self.header_name}"
                    )
                    return self.json(
                        {"status": "error", "message": "Unauthorized"}, status_code=401
                    )

            # Parse the JSON data
            data = await request.json()
            _LOGGER.debug(f"Received webhook data: '{json.dumps(data)}'")

            # Extract device info
            if CS_DEVICE_INFO_KEY not in data:
                return self.json(
                    {"status": "error", "message": "No deviceInfo in payload"}
                )

            device_info_raw = data[CS_DEVICE_INFO_KEY]
            dev_eui = device_info_raw.get(CS_DEVICE_EUI_KEY)

            if not dev_eui:
                return self.json(
                    {"status": "error", "message": "No devEui in deviceInfo"}
                )

            # Extract object data (sensor readings)
            object_data = data.get(CS_OBJECT_KEY, {})
            if not object_data or not isinstance(object_data, dict):
                return self.json(
                    {"status": "ignored", "message": "No valid object data"}
                )

            # Flatten the object data
            flat_data = flatten_dict(object_data)

            # Get device metadata
            rx_info = data.get(CS_RX_INFO_KEY, [{}])[0]
            device_info = {
                CS_DEVICE_NAME_KEY: device_info_raw.get(
                    CS_DEVICE_NAME_KEY, f"Device {dev_eui}"
                ),
                CS_TENANT_NAME_KEY: device_info_raw.get(
                    CS_TENANT_NAME_KEY, CS_TENANT_NAME_DEFAULT
                ),
                CS_DEVICE_PROFILE_NAME_KEY: device_info_raw.get(
                    CS_DEVICE_PROFILE_NAME_KEY, CS_DEVICE_PROFILE_NAME_DEFAULT
                ),
                CS_GATEWAY_ID_KEY: rx_info.get(
                    CS_GATEWAY_ID_KEY, CS_GATEWAY_ID_DEFAULT
                ),
            }

            # Initialize device dictionary if needed
            device_id = dev_eui
            hass_data = self.hass.data[DOMAIN][self.entry_id]
            if device_id not in hass_data.get(DEVICES_KEY, {}):
                hass_data[DEVICES_KEY][device_id] = {}

            # Track new entities
            new_sensors = []
            new_binary_sensors = []

            # Process each data point
            for key, raw_value in flat_data.items():
                _LOGGER.debug(
                    f"Processing data point: {key} = {raw_value} ({type(raw_value).__name__})"
                )

                # Generate unique ID and friendly name
                unique_id = f"{device_id}_{key}"
                name_suffix = " ".join(
                    list(
                        map(lambda x: x.capitalize(), key.replace("_", " ").split(" "))
                    )
                )
                name = f"{device_info[CS_DEVICE_NAME_KEY]} {name_suffix}"

                # Sanitize the value
                sanitized_value = sanitize_value(raw_value, key)
                _LOGGER.debug(
                    f"Sanitized value: {sanitized_value} ({type(sanitized_value).__name__})"
                )

                # Check if entity already exists
                if key in hass_data[DEVICES_KEY].get(device_id, {}):
                    # Update existing entity
                    _LOGGER.debug(f"Updating existing entity: {name}")
                    entity = hass_data[DEVICES_KEY][device_id][key]
                    entity.update_state(sanitized_value)
                    continue

                detection_keys = [
                    object_data.get(CS_TYPE_REF_KEY, {}).get(key, None),
                    key,
                ]

                # Determine if boolean or sensor
                if isinstance(sanitized_value, bool):
                    # Create binary sensor
                    device_class = detect_binary_sensor_device_class(*detection_keys)
                    _LOGGER.info(f"Creating binary sensor: {name} = {sanitized_value}")
                    entity = ChirpstackBinarySensor(
                        device_id, device_class, name, unique_id, device_info
                    )
                    new_binary_sensors.append(entity)
                else:
                    # Create sensor with appropriate unit
                    unit, device_class = detect_sensor_unit(*detection_keys)
                    _LOGGER.info(f"Creating sensor: {name} = {sanitized_value} {unit}")
                    entity = ChirpstackSensor(
                        device_id, name, device_class, unit, unique_id, device_info
                    )
                    new_sensors.append(entity)

                # Store in devices dict
                hass_data[DEVICES_KEY].setdefault(device_id, {})[key] = entity
                entity.set_initial_value(sanitized_value)

            # Add new sensors to Home Assistant
            if new_sensors:
                platform_function = hass_data.get(ADD_SENSOR_ENTITIES_KEY)
                if platform_function:
                    _LOGGER.info(
                        f"Adding {len(new_sensors)} sensors to Home Assistant using {platform_function}"
                    )
                    try:
                        platform_function(new_sensors)
                        _LOGGER.info(
                            f"Successfully added sensors: {[s.name for s in new_sensors]}"
                        )
                    except Exception as e:
                        _LOGGER.error(f"Error adding sensors: {e}")
                        # Fall back to queuing
                        _LOGGER.info("Falling back to queuing sensors")
                        hass_data.setdefault(PENDING_SENSORS_KEY, []).extend(
                            new_sensors
                        )
                else:
                    _LOGGER.info(
                        f"Queueing {len(new_sensors)} sensors for later addition (platform function not available)"
                    )
                    hass_data.setdefault(PENDING_SENSORS_KEY, []).extend(new_sensors)
                    # Debug what's in the hass_data
                    _LOGGER.debug(f"Current hass_data keys: {list(hass_data.keys())}")

            # Add new binary sensors to Home Assistant
            if new_binary_sensors:
                if ADD_BINARY_SENSOR_ENTITIES_KEY in hass_data:
                    _LOGGER.info(
                        f"Adding {len(new_binary_sensors)} binary sensors to Home Assistant"
                    )
                    hass_data[ADD_BINARY_SENSOR_ENTITIES_KEY](new_binary_sensors)
                else:
                    _LOGGER.info(
                        f"Queueing {len(new_binary_sensors)} binary sensors for later addition"
                    )
                    hass_data.setdefault(PENDING_BINARY_SENSORS_KEY, []).extend(
                        new_binary_sensors
                    )

            # Return success
            return self.json(
                {
                    "status": "ok",
                    "device": device_info["deviceName"],
                    "sensors_added": len(new_sensors),
                    "binary_sensors_added": len(new_binary_sensors),
                }
            )

        except Exception as e:
            _LOGGER.exception(f"Error processing webhook: {e}")
            return self.json(
                {"status": "error", "message": f"Internal error: {str(e)}"},
                status_code=500,
            )
