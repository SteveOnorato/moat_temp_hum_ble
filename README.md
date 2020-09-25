# Home Assistant Integration for Moat Temperature/Humidity BLE Sensors

A custom component for [Home Assistant](https://www.home-assistant.io) that listens for the BLE (Bluetooth Low Energy) advertising packets broadcast by Moat Bluetooth Thermometer/Hygrometers.

## Supported Devices
* [Moat S2](https://www.amazon.com/dp/B08DK739F5)

## Installation


**1. Install the custom component:**

- The easiest way is to install it with [HACS](https://hacs.xyz/). First install [HACS](https://hacs.xyz/) if you don't have it yet. After installation, the custom component can be found in the HACS store under integrations.

- Alternatively, you can install it manually. Just copy & paste the content of the `moat_temp_hum_ble/custom_components` folder into your `config/custom_components` directory.
     As example, you will get the `sensor.py` file in the following path: `/config/custom_components/moat_temp_hum_ble/sensor.py`.

- If running Home Assistant without root access, the [Bleson](https://github.com/TheCellule/python-bleson) Python library used for accessing Bluetooth requires the following permissions applied to the Python 3 binary. If using a virtual environment for HA, this binary will be in the virtual environment path.

     *NOTE*: Replace "path" with the path to the Python3 binary (example: /srv/homeassistant/bin/python3)
     ```
     sudo setcap cap_net_raw,cap_net_admin+eip $(eval readlink -f path)
     ```
**2. Restart Home Assistant:**

- Restart Home Assistant to load the integration.
  
  You can use the UI: Configuration / Server Controls / RESTART.
- Make sure you do this **before** modifying configuration.yaml, otherwise the configuration won't be recognized and you'll get an error when clicking RESTART.

**3. Add the platform to your configuration.yaml file (see [below](#configuration))**

**4. Restart Home Assistant:**

- A second restart is required to load the configuration. Within a few minutes, the sensors should be added to your home-assistant automatically (at least one [period](#period) required).

**5. If the entities are still not displaying data, a restart of the host device may be required.**


### Configuration Variables

Specify the sensor platform `moat_temp_hum_ble` and a list of devices with unique MAC address.

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

##### Additional configuration options
| Option | Type |Default Value | Description |  
| -- | -- | -- | -- |
| `rounding`| Boolean | `True` | Enable/disable rounding of the average of all measurements taken within the number seconds specified with 'period'. |  
| `decimals` | positive integer | `2`| Number of decimal places to round if rounding is enabled. NOTE: the raw Celsius is rounded and setting `decimals: 0` will still result in decimal values returned for Fahrenheit as well as temperatures being off by up to 1 degree `F`.|
| `period` | positive integer | `60` | The period in seconds during which the sensor readings are collected and transmitted to Home Assistant after averaging. The Govee devices broadcast roughly once per second so this limits amount of mostly duplicate data stored in  Home Assistant's database. |
| `log_spikes` |  Boolean | `False` | Puts information about each erroneous spike in the Home Assistant log. |
| `use_median` | Boolean  | `False` | Use median as sensor output instead of mean (helps with "spiky" sensors). Please note that both the median and the mean values in any case are present as the sensor state attributes. |
| `hci_device`| string | `hci0` | HCI device name used for scanning. |


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
  