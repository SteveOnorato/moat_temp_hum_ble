"""Humidity/Temperature device to store raw measurements."""
from dataclasses import dataclass
from typing import List, Optional, Union
import statistics as sts
import logging

from homeassistant.util.temperature import celsius_to_fahrenheit
from .const import (
    HUMIDITY_MIN,
    HUMIDITY_MAX,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CreateDeviceParams:
    report_fahrenheit: bool
    decimal_places: Optional[int]
    log_spikes: bool
    temp_range_min: int
    temp_range_max: int
    description: Optional[str] = None


class SensorDevice:
    """Stores raw measurements and is reset each time period."""

    # Identity
    _mac: str

    # Configuration:
    _desc: Optional[str]
    _report_fahrenheit: bool  # True for Fahrenheit, False for Celsius.
    _decimal_places: Optional[int]  # Number of decimal places to round output to, or None for no rounding.
    _log_spikes: bool
    _temp_range_min: int
    _temp_range_max: int

    # Measurements:
    _num_measurements: int
    _rssi_measurements: List[int]
    _temperature_measurements: List[float]
    _humidity_measurements: List[float]
    _latest_battery_measurement: Optional[int]
    _latest_raw_data_str: Optional[str]

    def __init__(self, mac: str, device_params: CreateDeviceParams) -> None:
        """Init."""
        self._mac = mac
        self._desc = device_params.description
        self._report_fahrenheit = device_params.report_fahrenheit
        self._decimal_places = device_params.decimal_places
        self._log_spikes = device_params.log_spikes
        self._temp_range_min = device_params.temp_range_min
        self._temp_range_max = device_params.temp_range_max
        self.reset()

    def reset(self) -> None:
        """Clear all measurements."""
        self._num_measurements = 0
        self._rssi_measurements = []
        self._temperature_measurements = []
        self._humidity_measurements = []
        self._latest_battery_measurement = None
        self._latest_raw_data_str = None

    # Configuration:

    @property
    def mac(self) -> str:
        """Return MAC address."""
        return self._mac

    @property
    def decimal_places(self) -> Optional[int]:
        """Set number of decimal places for rounding value."""
        return self._decimal_places

    @decimal_places.setter
    def decimal_places(self, value: int) -> None:
        """Set number of decimal places for rounding value."""
        if value >= 0:
            self._decimal_places = value

    @property
    def description(self) -> Optional[str]:
        """Return device description or MAC address."""
        return self._mac if (self._desc is None) else self._desc

    @description.setter
    def description(self, value: str) -> None:
        """Set device description."""
        if isinstance(value, str):
            self._desc = value

    @property
    def log_spikes(self) -> bool:
        """Return if spikes will be logged (will be at ERROR level)."""
        return self._log_spikes

    @log_spikes.setter
    def log_spikes(self, value: bool) -> None:
        """Set if spikes will be logged (will be at ERROR level)."""
        self._log_spikes = value

    # Measurements:

    @property
    def num_measurements(self) -> int:
        """Number of measurements this period."""
        return self._num_measurements

    @property
    def last_raw_data(self) -> Optional[str]:
        """Return last raw data, for debugging and error reporting purposes."""
        return self._latest_raw_data_str

    @property
    def battery(self) -> Optional[int]:
        """Return battery remaining value."""
        return self._latest_battery_measurement

    @battery.setter
    def battery(self, value: Optional[int]) -> None:
        """Set battery remaining value."""
        if isinstance(value, int):
            self._latest_battery_measurement = value

    @property
    def rssi(self) -> Optional[int]:
        """Return RSSI value."""
        try:
            return round(sts.mean(self._rssi_measurements))
        except (AssertionError, sts.StatisticsError):
            return None

    @rssi.setter
    def rssi(self, value: Optional[int]) -> None:
        """Set RSSI value."""
        if isinstance(value, int) and value < 0:
            self._rssi_measurements.append(value)

    @property
    def mean_temperature(self) -> Optional[float]:
        """Mean temperature of values collected, or None if all samples were spikes."""
        try:
            avg = sts.mean(self._temperature_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        if self._report_fahrenheit:
            avg = celsius_to_fahrenheit(avg)
        if self._decimal_places is not None:
            avg = float(round(avg, self._decimal_places))
        return avg

    @property
    def median_temperature(self) -> Optional[float]:
        """Median temperature of values collected, or None if all samples were spikes."""
        try:
            avg = sts.median(self._temperature_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        if self._report_fahrenheit:
            avg = celsius_to_fahrenheit(avg)
        if self._decimal_places is not None:
            avg = float(round(avg, self._decimal_places))
        return avg

    @property
    def mean_humidity(self) -> Optional[float]:
        """Mean humidity of values collected, or None if all samples were spikes."""
        try:
            avg = sts.mean(self._humidity_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        if self._decimal_places is not None:
            return float(round(avg, self._decimal_places))
        return avg

    @property
    def median_humidity(self) -> Optional[float]:
        """Median humidity of values collected, or None if all samples were spikes."""
        try:
            avg = sts.median(self._humidity_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        if self._decimal_places is not None:
            return float(round(avg, self._decimal_places))
        return avg

    def update(self, temperature: Optional[float], humidity: Optional[float],
               packet: Optional[Union[int, str]]) -> None:
        # Check if temperature within bounds
        if temperature is not None and self._temp_range_min <= temperature <= self._temp_range_max:
            self._temperature_measurements.append(temperature)
        elif self._log_spikes:
            _LOGGER.error("Temperature spike: %r (%r)", temperature, self._mac)

        # Check if humidity within bounds
        if humidity is not None and HUMIDITY_MIN <= humidity <= HUMIDITY_MAX:
            self._humidity_measurements.append(humidity)
        elif self._log_spikes:
            _LOGGER.error("Humidity spike: %r (%r)", humidity, self._mac)

        self._latest_raw_data_str = str(packet)
        self._num_measurements += 1
