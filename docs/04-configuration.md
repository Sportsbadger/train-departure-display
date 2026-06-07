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

## ADS-B aircraft mode (optional)

ADS-B support is disabled by default. When enabled, the display can alternate between the existing train board and a nearby-aircraft board using readsb/tar1090 `aircraft.json` output.

| Key | Example Value
|-----|----------
| `adsbEnabled` | `True` (enables ADS-B mode as an available transport mode)
| `transportModes` | `train,adsb` (ordered comma-separated modes to display; use `adsb` for ADS-B only; defaults to `train`)
| `modeSwitchInterval` | `300` (seconds before switching to the next configured mode)
| `transportFallbackMode` | `train` (fallback shown if ADS-B fetch/parsing fails; set to anything else to show an ADS-B unavailable screen instead)
| `adsbSourceUrl` | `http://192.168.1.74/readsb/data/aircraft.json` (readsb/tar1090 JSON endpoint)
| `adsbHomeLat` | `51.501` (receiver/display latitude; required for ADS-B sorting)
| `adsbHomeLon` | `-0.142` (receiver/display longitude; required for ADS-B sorting)
| `adsbFetchTimeout` | `2` (HTTP timeout in seconds)
| `adsbUserAgent` | `Mozilla/5.0 TrainDepartureDisplay/ADS-B` (HTTP User-Agent sent to the ADS-B web proxy)
| `adsbRefreshTime` | `10` (seconds between ADS-B JSON refreshes while in ADS-B mode)
| `adsbDisplayCount` | `5` (nearest aircraft to keep for the aircraft board)
| `adsbMaxAgeSeconds` | `30` (ignore aircraft not seen within this many seconds)
| `adsbMaxDistanceNm` | `100` (optional maximum distance in nautical miles; blank means no distance cap)
| `adsbMinAltitudeFt` | `1000` (optional minimum altitude in feet; blank means no altitude floor)
| `adsbRouteLookupEnabled` | `False` (enables a second-stage tar1090-compatible route lookup for origin/destination)
| `adsbRouteApiUrl` | `https://api.adsb.lol/api/0/routeset` (route lookup endpoint accepting a `planes` JSON POST body)
| `adsbRouteFetchTimeout` | `4` (HTTP timeout in seconds for the route lookup request)
| `adsbRouteDisplay` | `iata` (route label format: `iata`, `icao`, or `city`)

The ADS-B board skips aircraft without positions, because nearest-aircraft sorting requires latitude and longitude. When `adsbRouteLookupEnabled` is true, the app keeps the existing readsb/tar1090 aircraft JSON as the live aircraft source, then POSTs the displayed aircraft callsigns and positions to the configured `adsbRouteApiUrl`. Returned origin/destination data is best-effort and appears at the start of the highlighted aircraft detail line when available. The highlighted full-detail aircraft cycles through all displayed aircraft using `loopDepartureInterval`; the lower ADS-B rows show the remaining aircraft summaries. ADS-B JSON is refreshed in the background and cached before/while the mode is displayed, so slow reads do not block OLED animation or mode transitions. Network failures and malformed ADS-B JSON are handled separately from train loading so the train board can continue to run. The default `adsbUserAgent` avoids reverse proxy bot blocks that reject the default Python requests User-Agent.

## Plane-Alert mode (optional)

Plane-Alert support is disabled by default. When enabled, the display can alternate to a docker-planefence Plane-Alert board using the `pa_query.php` JSON API exposed by the Plane-Alert web UI. Use the exact `pa_query.php` path from your Plane-Alert installation; for example, if PlaneFence is served from `/planefence`, use `/planefence/pa_query.php` rather than adding `/plane-alert`.

| Key | Example Value
|-----|----------
| `planeAlertEnabled` | `True` (enables Plane-Alert mode as an available transport mode)
| `transportModes` | `train,adsb,plane-alert` (ordered comma-separated modes to display; `planealert` is also accepted; defaults to `train`)
| `modeSwitchInterval` | `300` (seconds before switching to the next configured mode)
| `transportFallbackMode` | `train` (fallback shown if Plane-Alert fetch/parsing fails; set to anything else to show a Plane-Alert unavailable screen instead)
| `planeAlertSourceUrl` | `http://192.168.1.74/planefence/pa_query.php?timestamp=.*&type=json` (Plane-Alert JSON endpoint; include at least one query parameter because docker-planefence requires it)
| `planeAlertFetchTimeout` | `15` (HTTP timeout in seconds; increase this if the browser works but the app times out)
| `planeAlertUserAgent` | `Mozilla/5.0 TrainDepartureDisplay/Plane-Alert` (HTTP User-Agent sent to the Plane-Alert web proxy)
| `planeAlertRefreshTime` | `30` (seconds between Plane-Alert background JSON refresh attempts)
| `planeAlertDisplayCount` | `5` (total Plane-Alert aircraft to show: the latest highlighted alert plus the remaining aircraft in the lower scrolling rows)
| `planeAlertMaxAgeHours` | `24` (optional maximum alert age in hours; blank means no age cap)

The Plane-Alert board sorts alerts newest first using the `timestamp` field, then displays callsign, tail/hex, equipment, owner/name, first-observed position, and observed time when present. Plane-Alert JSON is refreshed in the background and cached before/while the mode is displayed, so slow history queries do not block OLED animation or mode transitions. The example `planeAlertSourceUrl` queries all timestamps; for large Plane-Alert histories, prefer a narrower docker-planefence regex query or increase `planeAlertFetchTimeout`.

If using two screens the following line needs to be added into /boot/config.txt which is achieved by using the 'Define DT overlays' option within the Device configuration screen on balenaCloud: `spi1-3cs`

![](images/overlays.png)
