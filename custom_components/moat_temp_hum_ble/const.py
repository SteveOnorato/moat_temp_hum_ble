"""Constants for the BLE HCI monitor sensor integration."""

from enum import Enum

# Configuration options
CONF_REPORT_FAHRENHEIT = "report_fahrenheit"
CONF_ROUNDING = "rounding"
CONF_DECIMALS = "decimals"
CONF_PERIOD_SECS = "period_secs"
CONF_LOG_SPIKES = "log_spikes"
CONF_UPDATE_WHEN_UNAVAILABLE = "update_when_unavailable"
CONF_USE_MEDIAN = "use_median"
CONF_TEMP_RANGE_MIN_CELSIUS = "temp_range_min_celsius"
CONF_TEMP_RANGE_MAX_CELSIUS = "temp_range_max_celsius"
CONF_TEMPERATURE_ENTITIES = "temperature_entities"
CONF_HUMIDITY_ENTITIES = "humidity_entities"
CONF_BATTERY_ENTITIES = "battery_entities"
CONF_NUM_SAMPLES_ENTITIES = "num_samples_entities"
CONF_RSSI_ENTITIES = "rssi_entities"
CONF_HCI_DEVICE = "hci_device"
CONF_MOAT_DEVICES = "moat_devices"
CONF_GOVEE_DEVICES = "govee_devices"
CONF_DEVICE_MAC = "mac"
CONF_DEVICE_NAME = "name"
CONF_DEVICE_CALIBRATE_TEMP = "calibrate_temp"
CONF_DEVICE_CALIBRATE_HUMIDITY = "calibrate_humidity"

# Default values for configuration options
DEFAULT_REPORT_FAHRENHEIT = False
DEFAULT_ROUNDING = True
DEFAULT_DECIMALS = 2
DEFAULT_PERIOD = 60
DEFAULT_LOG_SPIKES = True
DEFAULT_UPDATE_WHEN_UNAVAILABLE = True
DEFAULT_USE_MEDIAN = False
DEFAULT_TEMP_RANGE_MIN = -45.0
DEFAULT_TEMP_RANGE_MAX = 70.0
DEFAULT_TEMPERATURE_ENTITIES = True
DEFAULT_HUMIDITY_ENTITIES = True
DEFAULT_BATTERY_ENTITIES = False
DEFAULT_RSSI_ENTITIES = False
DEFAULT_NUM_SAMPLES_ENTITIES = False
DEFAULT_HCI_DEVICE = "hci0"
DEFAULT_DEVICE_CALIBRATE_TEMP = 0.0
DEFAULT_DEVICE_CALIBRATE_HUMIDITY = 0.0

# Fixed constants:

# Sensor measurement limits to exclude erroneous spikes from the results
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 99.9


class DeviceBrand(Enum):
    MOAT = 1
    GOVEE = 2
