"""Thermometer/hygrometer BLE advertisement parser, supports Moat and Govee devices."""
import logging
from typing import Optional

from bleson.core.hci.constants import (
    GAP_FLAGS,
    GAP_NAME_COMPLETE,
    GAP_SERVICE_DATA,
    GAP_MFG_DATA,
)
from bleson.core.hci.type_converters import (
    rssi_from_byte,
    hex_string,
)
###############################################################################
from .const import DeviceBrand

_LOGGER = logging.getLogger(__name__)


def twos_complement(n: int, w: int = 16) -> int:
    """Two's complement integer conversion."""
    # Adapted from: https://stackoverflow.com/a/33716541.
    if n & (1 << (w - 1)):
        n = n - (1 << w)
    return n


#
# Reverse MAC octet order, return as a string
#
def reverse_mac(mac_bytes: bytes) -> Optional[str]:
    """Change LE order to BE."""
    if len(mac_bytes) != 6:
        return None
    octets = [format(c, "02x") for c in list(reversed(mac_bytes))]
    return (":".join(octets)).upper()


def little_endian_to_unsigned_int(bytes_to_convert: bytes) -> int:
    return int.from_bytes(bytes_to_convert, byteorder='little', signed=False)


def rescale_clamped(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    if value >= in_max:
        return out_max
    elif value <= in_min:
        return out_min
    else:
        return out_min + (out_max - out_min) * (value - in_min) / (in_max - in_min)


def moat_s2_battery_voltage_to_percentage(battery_voltage: int) -> float:
    return rescale_clamped(battery_voltage, 2760, 2820, 1.0, 100.0)


class TempHumAdvertisement:
    """Thermometer/hygrometer BLE sensor advertisement parser class."""

    name: Optional[str]
    mfg_data: bytes  # The manufacturer-specific data from the advertisement.
    temperature: Optional[float]
    humidity: Optional[float]
    battery: Optional[int]
    mac: Optional[str]
    rssi: Optional[int]
    _address: bytes

    def __init__(self, data: bytes, brand: DeviceBrand):
        """Init."""
        try:
            self._address = data[3:9]
            self.mac = reverse_mac(self._address)
            self.rssi = rssi_from_byte(data[-1])
            self.raw_data = data[10:-1]
            self.flags = 6
            self.name = None
            self.packet = None
            self.temperature = None
            self.humidity = None
            self.battery = None

            #  Byte 0: Num reports to follow (we only expect 01)
            #  Byte 1: GAP ADV type (can be 00=ADV_IND or 04=SCAN_RSP)
            #  Byte 2: GAP Addr type (Govees send 00=LE_PUBLIC_ADDRESS, Moats send 01=LE_RANDOM_ADDRESS)
            #  Bytes 3-8: MAC address (reverse byte order)
            #  Byte 9: Length (not counting header or final RSSI byte, so should be 11 less than the data raw_data size)
            #  Bytes 10-(-1): raw_data
            #    Byte 0: GAP (Generic Access Profile) length
            #    Byte 1: GAP type
            #    Bytes 2-(length): payload
            #  Byte (-1): Signal Power (RSSI at 1 foot as measured by the transmitter's manufacturer)

            pos = 10
            while pos < len(data) - 1:
                length = data[pos]
                payload_offset = pos + 2
                gap_type = data[pos + 1]
                payload_end = payload_offset + length - 1
                payload = data[payload_offset:payload_end]
                _LOGGER.debug("Pos=%d Type=%02x Len=%d Payload=%s", pos, gap_type, length, hex_string(payload))
                if GAP_FLAGS == gap_type:
                    self.flags = payload[0]
                    _LOGGER.debug("Flags=%02x", self.flags)
                elif GAP_NAME_COMPLETE == gap_type:
                    self.name = str(payload)
                    _LOGGER.debug("Complete Name=%s", self.name)
                elif GAP_SERVICE_DATA == gap_type:
                    self.mfg_data = payload
                    _LOGGER.debug("Service Data=%s", hex_string(self.mfg_data))
                elif GAP_MFG_DATA == gap_type:
                    self.mfg_data = payload
                    _LOGGER.debug("Manufacturer Data=%s", hex_string(self.mfg_data))
                pos += length + 1

            # Not all advertisements contain the measurement data.
            if (brand is DeviceBrand.MOAT) and self.check_is_moat_s2():
                # Conversions were kindly provided by the Moat developer, Erik Laybourne:
                timestamp = little_endian_to_unsigned_int(self.mfg_data[8:12])
                self.temperature = -46.85 + 175.72 * (little_endian_to_unsigned_int(self.mfg_data[12:14]) / 65536.0)
                self.humidity = -6.0 + 125.0 * (little_endian_to_unsigned_int(self.mfg_data[14:16]) / 65536.0)
                battery_voltage = little_endian_to_unsigned_int(self.mfg_data[16:18])
                self.battery = int(moat_s2_battery_voltage_to_percentage(battery_voltage))
                self.packet = hex_string(self.mfg_data[8:18]).replace(" ", "")
                _LOGGER.debug("Moat S2:%s: %d: %d", self.mac, timestamp, battery_voltage)
            elif brand is DeviceBrand.GOVEE:
                if self.check_is_gvh5075_gvh5072():
                    mfg_data_5075 = hex_string(self.mfg_data[3:6]).replace(" ", "")
                    self.packet = int(mfg_data_5075, 16)
                    self.temperature = (self.packet // 1000) / 10.0
                    self.humidity = (self.packet % 1000) / 10.0
                    self.battery = int(self.mfg_data[6])
                elif self.check_is_gvh5102():
                    mfg_data_5075 = hex_string(self.mfg_data[4:7]).replace(" ", "")
                    self.packet = int(mfg_data_5075, 16)
                    self.temperature = (self.packet // 1000) / 10.0
                    self.humidity = (self.packet % 1000) / 10.0
                    self.battery = int(self.mfg_data[7])
                elif self.check_is_gvh5074() or self.check_is_gvh5051():
                    mfg_data_5074 = hex_string(self.mfg_data[3:7]).replace(" ", "")
                    temp_lsb = mfg_data_5074[2:4] + mfg_data_5074[0:2]
                    hum_lsb = mfg_data_5074[6:8] + mfg_data_5074[4:6]
                    self.packet = temp_lsb + hum_lsb
                    self.humidity = float(int(hum_lsb, 16) / 100)
                    # Negative temperature stored an two's complement
                    temp_lsb_int = int(temp_lsb, 16)
                    self.temperature = float(twos_complement(temp_lsb_int) / 100)
                    self.battery = int(self.mfg_data[7])
            else:
                return
            _LOGGER.debug("Read=%s %f %f %d (%s) %r",
                         self.mac, self.temperature, self.humidity, self.battery, self.packet, self.rssi)
        except (ValueError, IndexError):
            pass

    def check_is_gvh5074(self) -> bool:
        """Check if mfg data is that of Govee H5074."""
        return self._mfg_data_check(9, 6)

    def check_is_gvh5102(self) -> bool:
        """Check if mfg data is that of Govee H5102."""
        return self._mfg_data_check(8, 5) and self._mfg_data_service_uuid_check("0100")

    def check_is_gvh5075_gvh5072(self) -> bool:
        """Check if mfg data is that of Govee H5075 or H5072."""
        return self._mfg_data_check(8, 5) and self._mfg_data_service_uuid_check("88ec")

    def check_is_gvh5051(self) -> bool:
        """Check if mfg data is that of Govee H5051."""
        return self._mfg_data_check(11, 6)

    def check_is_moat_s2(self) -> bool:
        """Check if mfg data is that of Moat S2."""
        return self._mfg_data_check(20, 6) and self._mfg_data_service_uuid_check("0010")

    def _mfg_data_check(self, data_length: int, flags: int) -> bool:
        """Check if mfg data is of a certain length with the correct flag."""
        return (
                hasattr(self, "mfg_data")
                and len(self.mfg_data) == data_length
                and self.flags == flags
        )

    def _mfg_data_service_uuid_check(self, service_uuid: str) -> bool:
        """Check if mfg data id is of a certain value."""
        return (
                hasattr(self, "mfg_data")
                and len(self.mfg_data) > 2
                and hex_string(self.mfg_data[0:2]).replace(" ", "") == service_uuid
        )


def parse_ble_advertisement(data: bytes, brand: DeviceBrand) -> TempHumAdvertisement:
    return TempHumAdvertisement(data, brand)