# Home Assistant Integration for Moat Temperature/Humidity BLE Sensors

A custom component for [Home Assistant](https://www.home-assistant.io) that listens for the BLE (Bluetooth Low Energy) advertising packets broadcast by Moat Bluetooth Thermometer/Hygrometers.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=plastic)](https://github.com/custom-components/hacs)

## Supported Devices
* [Moat S2](https://www.amazon.com/dp/B08DK739F5)
* Select Govee BLE Sensors


## Installation


**1. Install the custom component:**

- The easiest way is to install it with [HACS](https://hacs.xyz/).
  - First install [HACS](https://hacs.xyz/) if you don't have it yet.
  - Click on "HACS" in the Home Assistant UI sidebar to display the "Home Assistant Community Store" page.
  - Click "Integrations".
  - Click the vertical ellipsis in the top-right, choose "Custom repositories"
    - Choose "Integration" as the Category.
    - Paste in the custom repository URL: https://github.com/SteveOnorato/moat_temp_hum_ble
    - Click "ADD".
    - Click "X" to close the dialog.
  - Click "INSTALL" under the new "Moat BLE Temperature/Humidity Sensor" item.

- Alternatively, you can install it manually. Just copy & paste the content of the `moat_temp_hum_ble/custom_components` folder into your `config/custom_components` directory.
     As example, you will get the `sensor.py` file in the following path: `/config/custom_components/moat_temp_hum_ble/sensor.py`.

*NOTE:* the following instructions about setting device permissions are an edge case for a very specific set up.  (If you do not understand, do not worry about it).
- If running Home Assistant without root access, the [Bleson](https://github.com/TheCellule/python-bleson) Python library used for accessing Bluetooth requires the following permissions applied to the Python 3 binary. If using a virtual environment for HA, this binary will be in the virtual environment path.

     *NOTE*: Replace "path" with the path to the Python3 binary (example: /srv/homeassistant/bin/python3)
     ```
     sudo setcap cap_net_raw,cap_net_admin+eip $(eval readlink -f path)
     ```
**2. Restart Home Assistant:**

- Restart Home Assistant to load the integration.
  
  You can use the UI: Configuration / Server Controls / RESTART.
- Make sure you do this **before** modifying configuration.yaml, otherwise the configuration won't be recognized and you'll get an error when clicking RESTART.

**3. Add the platform to your configuration.yaml file (see [below](#configuration-variables))**

**4. Restart Home Assistant:**

- A second restart is required to load the configuration. Within a few minutes, the sensors should be added to your home-assistant automatically (wait at least period_secs).

**5. If the entities are still not displaying data, a restart of the host device may be required.**


### Configuration Variables

In **configuration.yaml**, specify the sensor platform `moat_temp_hum_ble` and a list of devices with unique MAC address.

#### Simple configuration example:
*NOTE*: device name is optional.  If not provided, devices will be labeled using the MAC address.
```
sensor:
  - platform: moat_temp_hum_ble
    moat_devices:
      - mac: "A4:C1:38:A1:A2:A3"
        name: Bedroom
      - mac: "A4:C1:38:B1:B2:B3"
      - mac: "A4:C1:38:C1:C2:C3"
        name: Kitchen
```

There are multiple ways to learn the MAC addresses for your Bluetooth devices.
##### Windows
* Use https://www.microsoft.com/en-us/p/bluetooth-le-explorer/9n0ztkf1qd98?activetab=pivot:overviewtab (thanks, @iamhueman)
##### macOS
* Use packetlogger.app from "Additional Tools for XCode" https://developer.apple.com/download/more/?=packetlogger (thanks, @tronicdude)
##### Home Assistant Operating System (formerly HassOS):
* Enable the SSH & Web Terminal Add-on under Supervisor -> Dashboard (see https://community.home-assistant.io/t/home-assistant-community-add-on-ssh-web-terminal/33820).
  * You likely need to disable 'Protection mode' for SSH & Web Terminal and restart the add-on (to enable docker commands)
* Then, use the Web Terminal to run the following:
```
docker exec -it $(docker ps -f name=homeassistant -q) bash
hciconfig hci0 down
hciconfig hci0 up
hcitool -i hci0 lescan | grep -i 'Govee\|GVH\|Moat'
```
* Leave this running for a bit and it will display the matching devices as it hears from them.
* Hit Ctrl+C when done.
* You might want to re-enable 'Protection mode' for SSH & Web Terminal at this point.

#### Additional platform configuration options
| Option | Type |Default Value | Description |  
| -- | -- | -- | -- |
| `report_fahrenheit` | Boolean | `False` | True for Fahrenheit, False for Celsius. |
| `rounding`| Boolean | `True` | Enable/disable rounding of the measurements reported to Home Assistant.  (Either way, we always use maximum precision while collecting the data points to be averaged each `period`.)  NOTE: By default, this will round as Celsius, but if 'report_fahrenheit' is True, this will round as Fahrenheit.  If the Home Assistant UI converts to the other unit (due to global preference), you may see more decimal places than expected. |
| `decimals` | positive integer | `2`| Number of decimal places to round to (only if `rounding` is enabled). |
| `period_secs` | positive integer | `60` | The amount of time, in seconds, during which the sensor readings are collected before reporting the average to Home Assistant. The devices broadcast roughly once per second, so this limits the amount of mostly duplicate data stored in Home Assistant's database. |
| `log_spikes` | Boolean | `True` | Puts information about each erroneous spike in the Home Assistant log. |
| `update_when_unavailable` | Boolean | `True` | Determines the behavior when no measurements are received during a reporting period. If True, sets the temperature/humidity/RSSI/battery states to "unavailable". If False, the temperature/humidity/RSSI/battery states will not be updated (this will cause Home Assistant to keep showing the previous value, even though it may be out-of-date). |
| `use_median` | Boolean  | `False` | Use median as sensor output instead of mean (helps with "spiky" sensors). Either way, both the median and the mean values are present in the device state attributes (which can be used to make Template Sensors). |
| `temp_range_min_celsius` | float | `-45.0` | Can set the lower bound of reasonable measurements, in Celsius (even if `report_fahrenheit` is enabled).  Temperature measurements lower than this will be discarded. |
| `temp_range_max_celsius` | float | `70.0` | Can set the upper bound of reasonable measurements, in Celsius (even if `report_fahrenheit` is enabled).  Temperature measurements higher than this will be discarded. |
| `temperature_entities` | Boolean  | `True` | Can disable this if you don't want the temperature entities for the sensor devices. |
| `humidity_entities` | Boolean  | `True` | Can disable this if you don't want the humidity entities for the sensor devices. |
| `battery_entities` | Boolean  | `False` | Can enable this if you want a separate entity to track the battery percentage for each sensor device. |
| `num_samples_entities` | Boolean  | `False` | Can enable this if you want a separate entity to track the number of samples received each period for each sensor device. |
| `rssi_entities` | Boolean  | `False` | Can enable this if you want a separate entity to track the RSSI for each sensor device. |
| `hci_device`| string | `hci0` | HCI device name used for scanning.  May need to be changed if you have multiple Bluetooth adapters connected. |
| `govee_devices` | list of objects | None | Same format as `moat_devices`, but supports (BLE mode only) for Govee sensors H5051, H5072, H5074, H5075, H5101, H5102, and H5177.  I use this because the "python-bleson" library used here only supports 1 scan at a time, so this integration can't successfully run at the same time as https://github.com/Home-Is-Where-You-Hang-Your-Hack/sensor.goveetemp_bt_hci |

#### Additional device configuration options
| Option | Type |Default Value | Description |  
| -- | -- | -- | -- |
| `calibrate_temp` | float | `0.0` | Add this amount to each temperature measurement for this device (in degrees Fahrenheit or Celsius, depending on the "report_fahrenheit" setting). |
| `calibrate_humidity` | float | `0.0` | Add this amount to each humidity measurement for this device (in %). |

#### Full configuration example:
```
sensor:
  - platform: moat_temp_hum_ble
    report_fahrenheit: True
    rounding: True
    decimals: 1
    period_secs: 60
    log_spikes: True
    update_when_unavailable: True
    use_median: False
    temp_range_min_celsius: -45.0
    temp_range_max_celsius: 70.0
    temperature_entities: True
    humidity_entities: True
    battery_entities: False
    num_samples_entities: True
    rssi_entities: False
    hci_device: hci0
    moat_devices:
      - mac: "DE:49:A1:A2:A3:A4"
        name: Deep Freezer
        calibrate_temp: -0.55
        calibrate_humidity: -3.0
      - mac: "DE:49:C1:C2:C3:C4"
        name: Kitchen
        calibrate_temp: 2.2
    govee_devices:
      - mac: "A4:C1:38:A1:A2:A3"
        name: Bedroom
        calibrate_temp: 0.4
```

### Debugging
To enable logging for this component, add the following to configuration.yaml:
```
logger:
  logs:
    custom_components.moat_temp_hum_ble: debug
```


## Credits
  This was forked from https://github.com/Home-Is-Where-You-Hang-Your-Hack/sensor.goveetemp_bt_hci, which itself was based on [custom-components/sensor.mitemp_bt](https://github.com/custom-components/sensor.mitemp_bt).
  So, a big thank you to [@Thrilleratplay](https://community.home-assistant.io/u/thrilleratplay), [@tsymbaliuk](https://community.home-assistant.io/u/tsymbaliuk), and [@Magalex](https://community.home-assistant.io/u/Magalex)!
  
