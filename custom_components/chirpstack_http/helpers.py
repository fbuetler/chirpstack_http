import re
from homeassistant.const import UnitOfConductivity, UnitOfTemperature, UnitOfElectricPotential
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
import logging


_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

SENSOR_DETECTION_MAP = [
    [
        r"temp",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS
    ],
    [
        r"humid",
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE
    ],
    [
        r"battery",
        SensorDeviceClass.BATTERY,
        PERCENTAGE
    ],
    [
        r"voltage",
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT
    ],
    [
        r"rssi",
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    ],
    [
        r"snr",
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS
    ],
    [
        r"( ec | ec$ |electrical.?conductivity)",
        SensorDeviceClass.CONDUCTIVITY,
        UnitOfConductivity.MILLISIEMENS_PER_CM
    ],
]

BINARY_SENSOR_DETECTION_MAP = [
    [
        r"closed|open",
        BinarySensorDeviceClass.DOOR,
    ],
    [
        r"motion",
        BinarySensorDeviceClass.MOTION,
    ],
    [
        r"open",
        BinarySensorDeviceClass.DOOR,
    ],
    [
        r"occupancy",
        BinarySensorDeviceClass.OCCUPANCY,
    ],
    [
        r"presence",
        BinarySensorDeviceClass.PRESENCE,
    ],
    [
        r"tamper",
        BinarySensorDeviceClass.TAMPER,
    ],
    [
        r"water",
        BinarySensorDeviceClass.MOISTURE
    ]
]
    
    
def detect_sensor_unit(*args):
    """Detect unit of measurement based on key name."""
    logging.debug(f"Detecting sensor unit from keys: {args}")
    
    for key in args:
        found_class = None
        found_unit = None
        if key is None:
            continue
        key_l = key.lower()
        key_u = key.upper()
        if "," in key:
            found_class,found_unit = key.split(",")
        if found_class or found_unit:
            
            found_class = found_class.strip()
            found_unit = found_unit.strip()
            if found_class.upper() in SensorDeviceClass.__dict__:
                return [found_unit, SensorDeviceClass.__dict__[found_class]]
            else:
                return [found_unit, None]
            
        for pattern, device_class, unit in SENSOR_DETECTION_MAP:
            if re.search(pattern, key_l):
                _LOGGER.debug(f"Detected sensor unit: {unit} and device class: {device_class} for key: {key}")
                return [unit, device_class]
        
        if key_u in SensorDeviceClass.__dict__:
            return [None, SensorDeviceClass.__dict__[key_u]]
        
        
    return [None,None]

def detect_binary_sensor_device_class(*args):
    """Detect unit of measurement based on key name."""
    for key in args:
        
        if key is None:
            continue
        key_l = key.lower()
        key_u = key.upper()
        
        for pattern, device_class in BINARY_SENSOR_DETECTION_MAP:
            if re.search(pattern, key_l):
                _LOGGER.debug(f"Detected binary sensor device class: {device_class} for key: {key}")
                return device_class
        
        if key_u in BinarySensorDeviceClass.__dict__:
            _LOGGER.debug(f"Detected binary sensor device class: {BinarySensorDeviceClass.__dict__[key_u]} for key: {key}")
            return BinarySensorDeviceClass.__dict__[key_u]
        
    return None