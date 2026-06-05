# Configuration

Sign up for the [National Rail Enquiries OpenLDBWS API](http://realtime.nationalrail.co.uk/OpenLDBWSRegistration), which will generate a token for you to use as the API key.

Only the API key is required to make the project run, everything else is optional but of course it may make sense for you to at least choose your preferred your station.

These environment variables are specified using the [balenaCloud dashboard](https://www.balena.io/docs/learn/manage/serv-vars/), allowing you to set up multiple signs in one fleet for different stations.


| Key                              | Example Value
|----------------------------------|----------
|`apiKey` **(REQUIRED)** | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (OpenLDBWS API key)
|`TZ`  | `Europe/London`, will default to UTC if not set ([timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones))
|`departureStation`  | `PAD` ([station code](https://www.nationalrail.co.uk/stations_destinations/48541.aspx))
|`destinationStation`  | `HWV` ([station code](https://www.nationalrail.co.uk/stations_destinations/48541.aspx)) [optional] Filters trains shown to only those that call at this station
|`timeOffset`  | `5` [optional] (Time offset, in minutes, for the departure board. Can be used to see into the future (positive value) or past (negative value). Set 5 if you live 5 min from the station and want to hide departures that are too soon to catch)
|`refreshTime` | `120` (seconds between data refresh)
|`screenRotation` | `2` (rotates the output of the OLED, 0 for when using the desk stand, 2 for the monitor mount ([docs](https://luma-oled.readthedocs.io/en/latest/api-documentation.html#luma.oled.device.ssd1322)))
|`operatingHours` | `8-22` (hours during which the data will refresh at the interval above - leave blank to run all day)
|`screenBlankHours` | `1-6` (hours during which the screen will be blank and data will not refresh - leave blank to never blank)
| `outOfHoursName` | `London Paddington` (name shown when current time is outside the `operatingHours`)
| `dualScreen` | `True` (if you are using two displays)
| `screen1Platform` | `1` (sets the platform you want to have displayed on the first or single-screen display)
| `screen2Platform` | `2` (sets the platform you want to have displayed on the second display)
| `individualStationDepartureTime` | `False` (Displays the estimated or scheduled time of the service at each leg of a journey)
| `fpsTime` | `4` (adjusts how often the effective FPS is displayed)
| `headless` | `True` (outputs to noop serial device rather than serial port; useful for running on a development machine)
| `showDepartureNumbers` | `True` (adds 1st / 2nd / 3rd as per UK train departures)
| `firstDepartureBold` | `False` (makes the first departure use either the bold or normal font)
| `loopDepartureCount` | `6` (number of upcoming departures, after the first, to loop through on the lower two rows)
| `loopDepartureInterval` | `10` (seconds between rotating the lower two rows to the next pair of departures)
| `targetFPS` | `20` (Frame rate regulator FPS target; 0 disables the regulator, which will increase FPS on constrained CPU, but will run the CPU hot at 100%.)
| `debug` | `False` (Display debugging information; `True` shows the debug info permanently, any integer `>1` will show instead of the splash screen for that number of seconds)
| `displayModes` | `train,plane` (`train` keeps the original train-only display. `plane` shows only ADS-B aircraft. `train,plane` alternates between both modes)
| `modeSwitchInterval` | `300` (seconds to show each mode before switching to the next configured mode)
| `adsbSourceType` | `readsb-json` (decoded ADS-B source type. Raw Beast decoding is intentionally not performed in the display loop)
| `adsbJsonUrl` | `http://192.168.1.50/tar1090/data/aircraft.json` (full URL for decoded readsb/tar1090 aircraft JSON; preferred ADS-B source setting)
| `adsbHost` | `192.168.1.50` (feeder host used when `adsbJsonUrl` is blank)
| `adsbJsonPort` | `80` (HTTP port used with `adsbHost`)
| `adsbJsonPath` | `/tar1090/data/aircraft.json` (aircraft JSON path used with `adsbHost`)
| `adsbReceiverLat` | `51.5000` (receiver latitude; required for plane mode nearest-aircraft sorting)
| `adsbReceiverLon` | `-0.1200` (receiver longitude; required for plane mode nearest-aircraft sorting)
| `adsbRefreshTime` | `5` (seconds between decoded ADS-B JSON polls)
| `adsbAircraftInterval` | `5` (seconds between aircraft shown on the plane display)
| `adsbMaxAircraft` | `8` (number of nearest aircraft to rotate through)
| `adsbMaxAge` | `30` (maximum aircraft age, in seconds, before it is dropped from the plane display)
| `adsbConnectTimeout` | `1.0` (ADS-B source connection timeout in seconds)
| `adsbReadTimeout` | `1.0` (ADS-B source read timeout in seconds)
| `adsbMaxDistanceNm` | `25` [optional] (maximum distance in nautical miles for aircraft shown)
| `adsbMinAltitude` | `1000` [optional] (minimum altitude in feet for aircraft shown)
| `adsbMaxAltitude` | `40000` [optional] (maximum altitude in feet for aircraft shown)
| `adsbBeastHost` | `192.168.1.50` [reserved] (raw Beast host, reserved for a future adapter)
| `adsbBeastPort` | `30005` [reserved] (raw Beast TCP port, reserved for a future adapter)

If using two screens the following line needs to be added into /boot/config.txt which is achieved by using the 'Define DT overlays' option within the Device configuration screen on balenaCloud: `spi1-3cs`

![](images/overlays.png)
