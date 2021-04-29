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
    calibrate_temp: float = 0.0
    calibrate_humidity: float = 0.0


class SensorDevice:
    """Stores raw measurements and is reset each time period."""

    # Identity
    _mac: str

    # Based on received packets, not reset each period.
    _detected_model: Optional[str]

    # Configuration:
    _desc: Optional[str]
    #: True for Fahrenheit, False for Celsius.
    _report_fahrenheit: bool
    #: Number of decimal places to round output to, or None for no rounding.
    _decimal_places: Optional[int]
    _log_spikes: bool
    _temp_range_min: int
    _temp_range_max: int
    #: When we report to HA, we will modify the temperature measurements by this
    #: amount (in degrees Fahrenheit or Celsius, depending on the "report_fahrenheit"
    #: setting).
    _calibrate_temp: float
    #: When we report to HA, we will modify the measurements by this amount (in %).
    _calibrate_humidity: float

    # Measurements (reset each period):
    _num_measurements: int
    _rssi_measurements: List[int]
    _temperature_measurements: List[float]
    _humidity_measurements: List[float]
    _battery_percentage_measurements: List[int]
    _battery_millivolt_measurements: List[int]
    _latest_raw_data_str: Optional[str]

    def __init__(self, mac: str, device_params: CreateDeviceParams) -> None:
        """Init."""
        self._mac = mac
        self._detected_model = None
        self._desc = device_params.description
        self._report_fahrenheit = device_params.report_fahrenheit
        self._decimal_places = device_params.decimal_places
        self._log_spikes = device_params.log_spikes
        self._temp_range_min = device_params.temp_range_min
        self._temp_range_max = device_params.temp_range_max
        self._calibrate_temp = device_params.calibrate_temp
        self._calibrate_humidity = device_params.calibrate_humidity
        self.reset()

    def reset(self) -> None:
        """Clear all measurements."""
        self._num_measurements = 0
        self._rssi_measurements = []
        self._temperature_measurements = []
        self._humidity_measurements = []
        self._battery_percentage_measurements = []
        self._battery_millivolt_measurements = []
        self._latest_raw_data_str = None

    @property
    def mac(self) -> str:
        """Return MAC address."""
        return self._mac

    @property
    def model(self) -> Optional[str]:
        """Return the auto-detected model."""
        return self._detected_model

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
    def battery_percentage(self) -> Optional[int]:
        """Return battery remaining value, as percentage."""
        try:
            return round(sts.mean(self._battery_percentage_measurements))
        except (AssertionError, sts.StatisticsError):
            return None

    @property
    def battery_millivolts(self) -> Optional[int]:
        """Return battery voltage, in millivolts."""
        try:
            return round(sts.mean(self._battery_millivolt_measurements))
        except (AssertionError, sts.StatisticsError):
            return None

    @property
    def rssi(self) -> Optional[int]:
        """Return RSSI value."""
        try:
            return round(sts.mean(self._rssi_measurements))
        except (AssertionError, sts.StatisticsError):
            return None

    def append_rssi(self, value: Optional[int]) -> None:
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
        calibrated_avg = avg + self._calibrate_temp
        if self._decimal_places is not None:
            calibrated_avg = float(round(calibrated_avg, self._decimal_places))
        _LOGGER.debug(
            "%s: reporting %s (%s + %s)",
            self.mac,
            calibrated_avg,
            avg,
            self._calibrate_temp,
        )
        return calibrated_avg

    @property
    def median_temperature(self) -> Optional[float]:
        """
        Median temperature of values collected, or None if all samples were spikes.
        """
        try:
            avg = sts.median(self._temperature_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        if self._report_fahrenheit:
            avg = celsius_to_fahrenheit(avg)
        calibrated_avg = avg + self._calibrate_temp
        if self._decimal_places is not None:
            calibrated_avg = float(round(calibrated_avg, self._decimal_places))
        _LOGGER.debug(
            "%s: reporting %s (%s + %s)",
            self.mac,
            calibrated_avg,
            avg,
            self._calibrate_temp,
        )
        return calibrated_avg

    @property
    def mean_humidity(self) -> Optional[float]:
        """Mean humidity of values collected, or None if all samples were spikes."""
        try:
            avg = sts.mean(self._humidity_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        calibrated_avg = avg + self._calibrate_humidity
        if self._decimal_places is not None:
            calibrated_avg = float(round(calibrated_avg, self._decimal_places))
        _LOGGER.debug(
            "%s: reporting %s (%s + %s)",
            self.mac,
            calibrated_avg,
            avg,
            self._calibrate_humidity,
        )
        return calibrated_avg

    @property
    def median_humidity(self) -> Optional[float]:
        """Median humidity of values collected, or None if all samples were spikes."""
        try:
            avg = sts.median(self._humidity_measurements)
        except (AssertionError, sts.StatisticsError):
            return None
        calibrated_avg = avg + self._calibrate_humidity
        if self._decimal_places is not None:
            calibrated_avg = float(round(calibrated_avg, self._decimal_places))
        _LOGGER.debug(
            "%s: reporting %s (%s + %s)",
            self.mac,
            calibrated_avg,
            avg,
            self._calibrate_humidity,
        )
        return calibrated_avg

    def set_model(self, model: Optional[str]) -> None:
        self._detected_model = model

    def update(
        self,
        temperature: Optional[float],
        humidity: Optional[float],
        battery_percentage: Optional[int],
        battery_millivolts: Optional[int],
        packet: Optional[Union[int, str]],
    ) -> None:
        # Check if temperature within bounds
        if (
            temperature is not None
            and self._temp_range_min <= temperature <= self._temp_range_max
        ):
            self._temperature_measurements.append(temperature)
        elif self._log_spikes:
            _LOGGER.warning("Temperature out of range: %r (%r)", temperature, self._mac)

        # Check if humidity within bounds
        if humidity is not None and HUMIDITY_MIN <= humidity <= HUMIDITY_MAX:
            self._humidity_measurements.append(humidity)
        elif self._log_spikes:
            _LOGGER.warning("Humidity out of range: %r (%r)", humidity, self._mac)

        # Check if battery % within bounds
        if battery_percentage is not None and 0 <= battery_percentage <= 100:
            self._battery_percentage_measurements.append(battery_percentage)
        elif self._log_spikes:
            _LOGGER.warning(
                "Battery percentage out of range: %r (%r)",
                battery_percentage,
                self._mac,
            )

        # Check if battery voltage is present (not all models report this).
        if battery_millivolts is not None:
            self._battery_millivolt_measurements.append(battery_millivolts)

        self._latest_raw_data_str = str(packet)
        self._num_measurements += 1
