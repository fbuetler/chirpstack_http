"""HTTP component for ChirpStack integration."""

import logging
import json

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .sensor import ChirpstackSensor
from .binary_sensor import ChirpstackBinarySensor
from .helpers import detect_sensor_unit, detect_binary_sensor_device_class
from .const import (
    ADD_BINARY_SENSOR_ENTITIES_FUNC_KEY,
    ADD_SENSOR_ENTITIES_FUNC_KEY,
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


def sanitize_value(value, key=None) -> StateType | bool:
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
        self.name = f"{API_URL_PREFIX}/{url_suffix}"
        self.url = f"{API_URL_PREFIX}/{url_suffix}"
        self.requires_auth = False

        # custom header
        self.header_name = header_name
        self.header_value = header_value

    async def post(self, request):
        """Handle POST requests for ChirpStack uplinks."""
        try:
            self.handle(request)
        except Exception as e:
            _LOGGER.exception(f"Error processing webhook: {e}")
            return self.json(
                {"status": "error", "message": f"Internal error: {str(e)}"},
                status_code=500,
            )

    async def handle(self, request):
        # Check for authentication header if configured
        if self.header_name and self.header_value:
            errors = self.ensure_authenticated(request.headers)
            if errors:
                return errors

        # Parse the JSON data
        data: dict = await request.json()
        _LOGGER.debug(f"Received webhook data: '{json.dumps(data)}'")

        # Extract device info
        device_info_raw: dict = data[CS_DEVICE_INFO_KEY]
        if not device_info_raw:
            return self.json({"status": "error", "message": "No deviceInfo in payload"})

        dev_eui: str = device_info_raw.get(CS_DEVICE_EUI_KEY)
        if not dev_eui:
            return self.json({"status": "error", "message": "No devEui in deviceInfo"})

        # Extract object data (sensor readings)
        object_data: dict = data.get(CS_OBJECT_KEY, {})
        if not object_data or not isinstance(object_data, dict):
            return self.json({"status": "ignored", "message": "No valid object data"})

        # Flatten the object data
        flat_data: dict = flatten_dict(object_data)

        # Get device metadata
        rx_info: dict = data.get(CS_RX_INFO_KEY, [{}])[0]
        device_info: dict[str, str] = {
            CS_DEVICE_NAME_KEY: device_info_raw.get(
                CS_DEVICE_NAME_KEY, f"Device {dev_eui}"
            ),
            CS_TENANT_NAME_KEY: device_info_raw.get(
                CS_TENANT_NAME_KEY, CS_TENANT_NAME_DEFAULT
            ),
            CS_DEVICE_PROFILE_NAME_KEY: device_info_raw.get(
                CS_DEVICE_PROFILE_NAME_KEY, CS_DEVICE_PROFILE_NAME_DEFAULT
            ),
            CS_GATEWAY_ID_KEY: rx_info.get(CS_GATEWAY_ID_KEY, CS_GATEWAY_ID_DEFAULT),
        }

        hass_data: dict = self.hass.data[DOMAIN][self.entry_id]
        new_sensors, new_binary_sensors = self.create_or_update_sensor(
            hass_data, dev_eui, device_info, flat_data
        )

        # Add new sensors to Home Assistant
        self.add_sensor(
            "sensors",
            hass_data,
            new_sensors,
            ADD_SENSOR_ENTITIES_FUNC_KEY,
            PENDING_SENSORS_KEY,
        )

        self.add_sensor(
            "binary sensors",
            hass_data,
            new_binary_sensors,
            ADD_BINARY_SENSOR_ENTITIES_FUNC_KEY,
            PENDING_BINARY_SENSORS_KEY,
        )

        return self.json(
            {
                "status": "ok",
                "device": device_info["deviceName"],
                "sensors_added": len(new_sensors),
                "binary_sensors_added": len(new_binary_sensors),
            }
        )

    def ensure_authenticated(self, headers):
        if self.header_name not in headers:
            _LOGGER.warning(f"Missing authentication header: {self.header_name}")
            return self.json(
                {"status": "error", "message": "Unauthorized"}, status_code=401
            )

        if headers.get(self.header_name) != self.header_value:
            _LOGGER.warning(
                f"Invalid authentication header value for: {self.header_name}"
            )
            return self.json(
                {"status": "error", "message": "Unauthorized"}, status_code=401
            )

        return None

    def create_or_update_sensor(
        self,
        hass_data: dict,
        device_id: str,
        device_info: dict[str, str],
        data: dict,
    ):
        # Initialize device dictionary if needed
        if device_id not in hass_data.get(DEVICES_KEY, {}):
            hass_data[DEVICES_KEY][device_id] = {}

        # Track new entities
        new_sensors: list[ChirpstackSensor] = []
        new_binary_sensors: list[ChirpstackBinarySensor] = []

        # Process each data point
        for key, raw_value in data.items():
            _LOGGER.debug(
                f"Processing data point: {key} = {raw_value} ({type(raw_value).__name__})"
            )

            # Generate unique ID and friendly name
            unique_id = f"{device_id}_{key}"
            name_suffix = " ".join(
                list(map(lambda x: x.capitalize(), key.replace("_", " ").split(" ")))
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

            # Determine if boolean or sensor
            key_type_hints = [data.get(CS_TYPE_REF_KEY, {}).get(key, None), key]
            if isinstance(sanitized_value, bool):
                # Create binary sensor
                device_class = detect_binary_sensor_device_class(*key_type_hints)
                _LOGGER.info(f"Creating binary sensor: {name} = {sanitized_value}")
                entity = ChirpstackBinarySensor(
                    device_id, unique_id, name, device_class, device_info
                )
                new_binary_sensors.append(entity)
            else:
                # Create sensor with appropriate unit
                unit, device_class = detect_sensor_unit(*key_type_hints)
                _LOGGER.info(f"Creating sensor: {name} = {sanitized_value} {unit}")
                entity = ChirpstackSensor(
                    device_id, unique_id, name, device_class, device_info, unit
                )
                new_sensors.append(entity)

            entity.set_initial_state(sanitized_value)

            # Store in devices dict
            hass_data[DEVICES_KEY].setdefault(device_id, {})[key] = entity

        return (new_sensors, new_binary_sensors)

    def add_sensor(
        self,
        type: str,
        hass_data: dict,
        new_sensors: list[ChirpstackSensor | ChirpstackBinarySensor],
        func_key: str,
        pending_key: str,
    ):
        if not new_sensors:
            return

        add_entities_func: AddConfigEntryEntitiesCallback = hass_data.get(func_key)
        if add_entities_func:
            _LOGGER.info(f"Adding {len(new_sensors)} {type} using {add_entities_func}")
            try:
                add_entities_func(new_sensors)
                _LOGGER.info(
                    f"Successfully added {type}: {[s.name for s in new_sensors]}"
                )
                return
            except Exception as e:
                _LOGGER.error(f"Error adding {type}: {e}")
                _LOGGER.info(f"Falling back to queuing {type}")
                # fallthrough

        _LOGGER.info(f"Queueing {len(new_sensors)} {type} for later addition")
        hass_data.setdefault(pending_key, []).extend(new_sensors)

        _LOGGER.debug(f"Current hass_data keys: {list(hass_data.keys())}")
