"""Integration with Home Assistant (data types, platform setup, and update loop).

Note that this file MUST be named sensor.py to match the top level name in configuration.yaml.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional, Dict, Any, Sequence, Union

import voluptuous as vol  # type: ignore

import homeassistant.helpers.config_validation as cv  # type: ignore
import homeassistant.util.dt as dt_util  # type: ignore
from bleson import get_provider, Adapter  # type: ignore
from bleson.core.hci.constants import EVT_LE_ADVERTISING_REPORT  # type: ignore
from bleson.core.hci.type_converters import hex_string  # type: ignore
from bleson.core.types import BDAddress  # type: ignore
from homeassistant.components import sensor
from homeassistant.components.sensor import PLATFORM_SCHEMA  # type: ignore
from homeassistant.const import (  # type: ignore
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_BATTERY_LEVEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity  # type: ignore
from homeassistant.helpers.event import track_point_in_utc_time  # type: ignore
from .const import *
from .const import DEFAULT_HUMIDITY_ENTITIES
from .sensor_device import SensorDevice, CreateDeviceParams
from .temp_hum_advertisement_parser import parse_ble_advertisement

###############################################################################

_LOGGER = logging.getLogger(__name__)

DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_MAC): cv.string,
        vol.Optional(CONF_DEVICE_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_REPORT_FAHRENHEIT, default=DEFAULT_REPORT_FAHRENHEIT): cv.boolean,
        vol.Optional(CONF_ROUNDING, default=DEFAULT_ROUNDING): cv.boolean,
        vol.Optional(CONF_DECIMALS, default=DEFAULT_DECIMALS): cv.positive_int,
        vol.Optional(CONF_PERIOD_SECS, default=DEFAULT_PERIOD): cv.positive_int,
        vol.Optional(CONF_LOG_SPIKES, default=DEFAULT_LOG_SPIKES): cv.boolean,
        vol.Optional(CONF_UPDATE_WHEN_UNAVAILABLE, default=DEFAULT_UPDATE_WHEN_UNAVAILABLE): cv.boolean,
        vol.Optional(CONF_USE_MEDIAN, default=DEFAULT_USE_MEDIAN): cv.boolean,
        vol.Optional(CONF_TEMP_RANGE_MIN_CELSIUS, default=DEFAULT_TEMP_RANGE_MIN): int,
        vol.Optional(CONF_TEMP_RANGE_MAX_CELSIUS, default=DEFAULT_TEMP_RANGE_MAX): int,
        vol.Optional(CONF_TEMPERATURE_ENTITIES, default=DEFAULT_TEMPERATURE_ENTITIES): cv.boolean,
        vol.Optional(CONF_HUMIDITY_ENTITIES, default=DEFAULT_HUMIDITY_ENTITIES): cv.boolean,
        vol.Optional(CONF_BATTERY_ENTITIES, default=DEFAULT_BATTERY_ENTITIES): cv.boolean,
        vol.Optional(CONF_RSSI_ENTITIES, default=DEFAULT_RSSI_ENTITIES): cv.boolean,
        vol.Optional(CONF_NUM_SAMPLES_ENTITIES, default=DEFAULT_NUM_SAMPLES_ENTITIES): cv.boolean,
        vol.Optional(CONF_HCI_DEVICE, default=DEFAULT_HCI_DEVICE): cv.string,
        vol.Optional(CONF_MOAT_DEVICES): vol.All([DEVICES_SCHEMA]),
        vol.Optional(CONF_GOVEE_DEVICES): vol.All([DEVICES_SCHEMA]),
    }
)


###############################################################################


# Entry point!
def setup_platform(hass: HomeAssistant, config, add_entities, discovery_info=None) -> None:
    """Entry point to our integration, called by Home Assistant."""

    _ = discovery_info  # unused, but required by interface

    _LOGGER.info("Starting Bluetooth LE Humidity/Temperature Sensor platform")

    device_wrappers: List[SensorDeviceWrapper] = []  # Data objects of configured devices

    from bleson.core.hci import HCIPacket

    def handle_meta_event(hci_packet: HCIPacket) -> None:
        """Handle received BLE data.

        This callback will be called by the HCISocketPoller thread started by the bleson library.
        """
        # We only care about BLE packets of type ADVERTISING_REPORT
        if hci_packet.subevent_code == EVT_LE_ADVERTISING_REPORT:
            packet_bd_address = BDAddress(hci_packet.data[3:9])

            for curr_wrapper in device_wrappers:
                # Only process packets from devices that were explicitly added to the HA configuration.
                if BDAddress(curr_wrapper.sensorDevice.mac) == packet_bd_address:
                    _LOGGER.debug("Received raw_data for %s, len %d (data %d): %s",
                                  packet_bd_address, hci_packet.length, hci_packet.length - 11,
                                  hex_string(hci_packet.data))
                    # parse raw_data data
                    parsed_advertisement = parse_ble_advertisement(hci_packet.data, curr_wrapper.brand)

                    # If the advertisement was parsed (raw_data was populated), update our values.
                    if parsed_advertisement.packet is not None:
                        curr_wrapper.sensorDevice.update(parsed_advertisement.temperature,
                                                         parsed_advertisement.humidity,
                                                         parsed_advertisement.battery,
                                                         parsed_advertisement.battery_millivolts,
                                                         parsed_advertisement.packet)

                    # Update RSSI (even if the advertisement didn't have measurement data)
                    curr_wrapper.sensorDevice.append_rssi(parsed_advertisement.rssi)

    def init_configured_devices() -> None:
        """
        Initialize tracking for all devices listed in our configuration and register their Entities to Home
        Assistant.
        """

        device_params = CreateDeviceParams(report_fahrenheit=config[CONF_REPORT_FAHRENHEIT],
                                           decimal_places=config[CONF_DECIMALS] if config[CONF_ROUNDING] else None,
                                           log_spikes=config[CONF_LOG_SPIKES],
                                           temp_range_min=config[CONF_TEMP_RANGE_MIN_CELSIUS],
                                           temp_range_max=config[CONF_TEMP_RANGE_MAX_CELSIUS])

        # Initialize a wrapper for each configured device.
        for config_dev in config[CONF_MOAT_DEVICES]:
            init_wrapper(config_dev, device_params, DeviceBrand.MOAT)
        for config_dev in config[CONF_GOVEE_DEVICES]:
            init_wrapper(config_dev, device_params, DeviceBrand.GOVEE)

    def init_wrapper(config_device, device_conf, brand: DeviceBrand):
        mac = config_device["mac"]
        device_conf.description = config_device.get("name", None)
        new_device = SensorDevice(mac, device_conf)
        # Initialize Home Assistant Entities
        name = config_device.get("name", mac)
        ha_entities: List[TempHumSensorEntity] = []
        if config[CONF_TEMPERATURE_ENTITIES]:
            ha_entities.append(TemperatureEntity(mac, name, device_conf.report_fahrenheit))
        if config[CONF_HUMIDITY_ENTITIES]:
            ha_entities.append(HumidityEntity(mac, name))
        if config[CONF_RSSI_ENTITIES]:
            ha_entities.append(RssiEntity(mac, name))
        if config[CONF_BATTERY_ENTITIES]:
            ha_entities.append(BatteryLevelEntity(mac, name))
        if config[CONF_NUM_SAMPLES_ENTITIES]:
            ha_entities.append(NumSamplesPerPeriodEntity(mac, name))
        new_wrapper = SensorDeviceWrapper(new_device, ha_entities, brand)
        device_wrappers.append(new_wrapper)

        add_entities(ha_entities)

    def report_device_data() -> None:
        """Move the collected data from each SensorDevice to the Home Assistant entities and reset the collected data.
        """
        use_median = config[CONF_USE_MEDIAN]

        _DEV_STATE_ATTR = "_device_state_attributes"
        num_measurements_attr = "last median of" if use_median else "last mean of"

        for curr_wrapper in device_wrappers:
            entities = curr_wrapper.hassEntities
            device = curr_wrapper.sensorDevice

            temp_num = device.num_measurements
            _LOGGER.debug("Last mfg data for %r: %r, count=%d", device.mac, device.last_raw_data,
                          temp_num)

            curr_entity_index = 0

            # Temperature (optional, based on config)
            if config[CONF_TEMPERATURE_ENTITIES]:
                temperature_mean = device.mean_temperature
                temperature_median = device.median_temperature
                entities[curr_entity_index].device_state_attributes["mean"] = temperature_mean
                entities[curr_entity_index].device_state_attributes["median"] = temperature_median
                entities[curr_entity_index].state = temperature_median if use_median else temperature_mean
                curr_entity_index += 1

            # Humidity (optional, based on config)
            if config[CONF_HUMIDITY_ENTITIES]:
                humidity_mean = device.mean_humidity
                humidity_median = device.median_humidity
                entities[curr_entity_index].device_state_attributes["mean"] = humidity_mean
                entities[curr_entity_index].device_state_attributes["median"] = humidity_median
                entities[curr_entity_index].state = humidity_median if use_median else humidity_mean
                curr_entity_index += 1

            # RSSI (optional, based on config)
            if config[CONF_RSSI_ENTITIES]:
                entities[curr_entity_index].state = device.rssi
                curr_entity_index += 1

            # Battery level (optional, based on config)
            if config[CONF_BATTERY_ENTITIES]:
                entities[curr_entity_index].state = device.battery_percentage
                curr_entity_index += 1

            # Number of samples per period (optional, based on config)
            if config[CONF_NUM_SAMPLES_ENTITIES]:
                entities[curr_entity_index].state = device.num_measurements
                curr_entity_index += 1

            # All entities get the basic [untracked] attributes
            for entity in entities:
                # Skip reporting 'None' if CONF_UPDATE_WHEN_UNAVAILABLE is false.
                # Note that NumSamplesPerPeriodEntity will still be updated, since that is always valid.
                if config[CONF_UPDATE_WHEN_UNAVAILABLE] or entity.state is not None:
                    dev_state_attrs = entity.device_state_attributes
                    dev_state_attrs["last raw data"] = device.last_raw_data
                    dev_state_attrs["rssi"] = device.rssi
                    dev_state_attrs[ATTR_BATTERY_LEVEL] = device.battery_percentage
                    # Only fill in "battery mV" if the device supports it.
                    # The hasattr case is to make sure we set it to None if it was previously filled in, but
                    # device.battery_millivolts is None due to no samples received this period.
                    if (device.battery_millivolts is not None) or hasattr(dev_state_attrs, "battery mV"):
                        dev_state_attrs["battery mV"] = device.battery_millivolts
                    dev_state_attrs[num_measurements_attr] = device.num_measurements

                    # TODO: even better, don't collect the data if it's disabled.
                    # Check if it's enabled to avoid:
                    #  WARNING (SyncWorker_9) [homeassistant.helpers.entity] Entity sensor.deep_freezer_temp is
                    #  incorrectly being triggered for updates while it is disabled. This is a bug in the
                    #  moat_temp_hum_ble integration
                    if entity.enabled:
                        entity.schedule_update_ha_state()
                    else:
                        _LOGGER.info("Entity %s is disabled; skip update.", entity.entity_id)

            # TODO: There is a race condition.
            # We are in a SyncWorker thread here, but the HCISocketPoller thread can
            # concurrently update our device (within handle_meta_event).
            if temp_num != device.num_measurements:
                _LOGGER.debug("Measurements changed from %s to %s!", temp_num, device.num_measurements)

            device.reset()

    def schedule_update_ble_loop() -> None:
        # update_ble_loop() will be called after CONF_PERIOD_SECS elapses.
        # (And in the meantime, the HCISocketPoller thread will make calls to our handle_meta_event callback.)
        point_in_time = dt_util.utcnow() + timedelta(seconds=config[CONF_PERIOD_SECS])
        track_point_in_utc_time(hass, update_ble_loop, point_in_time)  # type: ignore

    def update_ble_loop(now) -> None:
        """Update the Home Assistant Entities from our collected data and refresh the BLE scanning.

        This probably shouldn't run in the event loop due to start_scanning potentially blocking."""

        _ = now  # unused, but required by interface

        _LOGGER.debug("update_ble_loop called")

        try:
            # This seems to revive the scanning if someone does:
            # hciconfig hci0 down
            # hciconfig hci0 up
            adapter.start_scanning()

            report_device_data()
        except RuntimeError as error:
            _LOGGER.error("Error during update_ble_loop: %s", error)

        # update_ble_loop() will be called again after CONF_PERIOD_SECS elapses.
        schedule_update_ble_loop()

    ###########################################################################

    # Initialize bluetooth adapter and begin scanning.
    # XXX: only supports LinuxProvider implementation (other platforms don't have _handle_meta_event to monkey-patch).
    # XXX: only supports hci0 - hci9
    adapter: Adapter = get_provider().get_adapter(int(config[CONF_HCI_DEVICE][-1]))
    # Monkey-patch the BluetoothHCIAdapter.  Would be better if the Adapter interface exposed this functionality.
    setattr(adapter, "_handle_meta_event", handle_meta_event)
    hass.bus.listen("homeassistant_stop", adapter.stop_scanning)
    adapter.start_scanning()

    # Initialize configured devices
    init_configured_devices()

    # update_ble_loop() will first be called after CONF_PERIOD_SECS elapses.
    schedule_update_ble_loop()

    _LOGGER.info("Done setting up Bluetooth LE Humidity/Temperature Sensor platform")


class TempHumSensorEntity(Entity):
    """Base class for our HomeAssistant Entity classes."""

    def __init__(self, mac: str, entity_name: str, device_name: str, unique_id_prefix: str):
        """Initialize the Entity."""
        self._state: Union[None, str, int, float] = None
        self._battery = None
        self._mac = mac
        self._unique_id = f'{unique_id_prefix}_{mac.replace(":", "")}'
        self._entity_name = entity_name
        self._device_name = device_name
        self._device_state_attributes: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the UI-friendly name of the Entity."""
        return self._entity_name

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the Entity."""
        return self._state

    @state.setter
    def state(self, state: Union[None, str, int, float]) -> None:
        """Set the state of the Entity."""
        self._state = state

    @property
    def should_poll(self) -> bool:
        """Don't poll; we will call schedule_update_ha_state from within our periodic update_ble_loop."""
        return False

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return self._device_state_attributes

    @property
    def unique_id(self) -> str:
        """Return the persistent unique ID."""
        return self._unique_id

    @property
    def force_update(self) -> bool:
        """Force update."""
        return True

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return {
            "identifiers": {
                (sensor.DOMAIN, self._mac)
            },
            "name": self._device_name,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        _LOGGER.info("Adding entity %s (%s): %s", self.entity_id, self.unique_id, self.name)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        _LOGGER.info("Removing entity %s (%s): %s", self.entity_id, self.unique_id, self.name)


class TemperatureEntity(TempHumSensorEntity):
    """HomeAssistant Entity for tracking temperature."""

    def __init__(self, mac: str, device_name: str, report_fahrenheit: bool):
        TempHumSensorEntity.__init__(self,
                                     mac=mac,
                                     device_name=device_name,
                                     entity_name=f"{device_name} temp",
                                     unique_id_prefix="t")
        self._report_fahrenheit = report_fahrenheit

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT if self._report_fahrenheit else TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the Home Assistant device class."""
        return DEVICE_CLASS_TEMPERATURE


class HumidityEntity(TempHumSensorEntity):
    """HomeAssistant Entity for tracking humidity."""

    def __init__(self, mac: str, device_name: str):
        TempHumSensorEntity.__init__(self,
                                     mac=mac,
                                     device_name=device_name,
                                     entity_name=f"{device_name} humidity",
                                     unique_id_prefix="h")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "%"

    @property
    def device_class(self):
        """Return the Home Assistant device class."""
        return DEVICE_CLASS_HUMIDITY


class RssiEntity(TempHumSensorEntity):
    """HomeAssistant Entity for tracking RSSI."""

    def __init__(self, mac: str, device_name: str):
        TempHumSensorEntity.__init__(self,
                                     mac=mac,
                                     device_name=device_name,
                                     entity_name=f"{device_name} RSSI",
                                     unique_id_prefix="r")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "dBm"

    @property
    def device_class(self):
        """Return the Home Assistant device class."""
        return DEVICE_CLASS_SIGNAL_STRENGTH


class BatteryLevelEntity(TempHumSensorEntity):
    """HomeAssistant Entity for tracking battery level."""

    def __init__(self, mac: str, device_name: str):
        TempHumSensorEntity.__init__(self,
                                     mac=mac,
                                     device_name=device_name,
                                     entity_name=f"{device_name} battery level",
                                     unique_id_prefix="b")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "%"

    @property
    def device_class(self):
        """Return the Home Assistant device class."""
        return DEVICE_CLASS_BATTERY


class NumSamplesPerPeriodEntity(TempHumSensorEntity):
    """HomeAssistant Entity for tracking number of the number measurements made during a period of time."""

    def __init__(self, mac: str, device_name: str):
        TempHumSensorEntity.__init__(self,
                                     mac=mac,
                                     device_name=device_name,
                                     entity_name=f"{device_name} samples",
                                     unique_id_prefix="s")

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        return "samples/period"

    @property
    def device_class(self):
        """Return the Home Assistant device class."""
        return None


@dataclass
class SensorDeviceWrapper:
    sensorDevice: SensorDevice
    hassEntities: Sequence[TempHumSensorEntity]
    brand: DeviceBrand
