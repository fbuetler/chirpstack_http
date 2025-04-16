import re
from homeassistant.const import UnitOfConductivity, UnitOfTemperature, UnitOfElectricPotential
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.components.sensor import SensorDeviceClass

DETECTION_MAP = [
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
        r"( ec | ec$)",
        SensorDeviceClass.CONDUCTIVITY,
        UnitOfConductivity.MILLISIEMENS_PER_CM
    ],
]


def detect_unit(key):
    """Detect unit of measurement based on key name."""
    key_l = key.lower()
    
    for pattern, device_class, unit in DETECTION_MAP:
        if re.search(pattern, key_l):
            return [unit, device_class]
    return [None,None]

