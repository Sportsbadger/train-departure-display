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
| `lastLineText` | `****Last Line****` (end-of-list marker shown centered in ADS-B and Plane-Alert lower rows)
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
| `adsbTopLeftTemplate` | `{summary_left}` (highlight row left block)
| `adsbTopRightTemplate` | `{summary_right}` (highlight row right block)
| `adsbScrollTemplate` | `{detail}` (single scrolling row block; the default detail no longer includes `seen`)
| `adsbNextLeftTemplate` | `{loop_aircraft}` (next-aircraft detail left block)
| `adsbNextRightTemplate` | `{loop_info}` (next-aircraft detail right block)

The ADS-B board skips aircraft without positions, because nearest-aircraft sorting requires latitude and longitude. When `adsbRouteLookupEnabled` is true, the app keeps the existing readsb/tar1090 aircraft JSON as the live aircraft source, then POSTs the displayed aircraft callsigns and positions to the configured `adsbRouteApiUrl`. Returned origin/destination data is best-effort and appears on the highlighted aircraft top line when available. The highlighted full-detail aircraft cycles through all displayed aircraft using a slightly extended `loopDepartureInterval`; when the first aircraft is highlighted, the lower ADS-B rows show only the second and third aircraft, then the third and fourth when the second is highlighted, and so on. When the lower rows reach the end of the displayed aircraft list they show the configured `lastLineText` centered before the highlighted aircraft cycles back to the first entry. The ADS-B board also labels the clock row with `ADSB`. The default highlighted top line shows flight, route, registration, aircraft type, preferred speed, distance, and altitude. The highlighted scrolling detail line pauses briefly before moving, then shows description, bearing, track, ground speed, Mach, climb/descent rate, and squawk when those fields are available. Secondary aircraft rows default to rank, flight, and type on the left, with speed, distance, and altitude grouped on the right. ADS-B JSON is refreshed in the background and cached before/while the mode is displayed, so slow reads do not block OLED animation or mode transitions. Network failures and malformed ADS-B JSON are handled separately from train loading so the train board can continue to run. Empty `201` route responses are treated as no-route results rather than route parse failures. The default `adsbUserAgent` avoids reverse proxy bot blocks that reject the default Python requests User-Agent.

ADS-B display templates use `{variable}` placeholders. Available variables are: `{summary_left}`, `{summary_right}`, `{summary}`, `{detail}`, `{loop_aircraft}`, `{loop_info}`, `{position}`, `{position_ordinal}`, `{display_name}`, `{flight}`, `{registration}`, `{hex}`, `{route}`, `{origin}`, `{destination}`, `{aircraft_type}`, `{description}`, `{latitude}`, `{longitude}`, `{distance_nm}`, `{distance}`, `{bearing_deg}`, `{bearing}`, `{altitude_ft}`, `{altitude}`, `{ground_speed_kt}`, `{speed}`, `{ground_speed}`, `{true_air_speed_kt}`, `{true_air_speed}`, `{summary_speed}`, `{mach_value}`, `{mach}`, `{track_deg}`, `{heading}`, `{vertical_rate_fpm}`, `{vertical_rate}`, `{squawk}`, `{squawk_label}`, `{seen_seconds}`, and `{seen}`.

Example custom ADS-B layout:

```env
adsbTopLeftTemplate={display_name} {route}
adsbTopRightTemplate={registration} {aircraft_type} {altitude}
adsbScrollTemplate={description}  {bearing}  {heading}  {ground_speed}  {squawk_label}  {hex}
adsbNextLeftTemplate={position_ordinal} {display_name} {aircraft_type}
adsbNextRightTemplate={speed} {distance} {altitude}
```

## Plane-Alert mode (optional)

Plane-Alert support is disabled by default. When enabled, the display can alternate to a docker-planefence Plane-Alert board using the `pa_query.php` JSON API exposed by the Plane-Alert web UI. Use the exact `pa_query.php` path from your Plane-Alert installation; current docker-planefence serves Plane-Alert at `/plane-alert`, so the API endpoint is usually `/plane-alert/pa_query.php`.

| Key | Example Value
|-----|----------
| `planeAlertEnabled` | `True` (enables Plane-Alert mode as an available transport mode)
| `transportModes` | `train,adsb,plane-alert` (ordered comma-separated modes to display; `planealert` is also accepted; defaults to `train`)
| `modeSwitchInterval` | `300` (seconds before switching to the next configured mode)
| `transportFallbackMode` | `train` (fallback shown if Plane-Alert fetch/parsing fails; set to anything else to show a Plane-Alert unavailable screen instead)
| `planeAlertSourceUrl` | `http://192.168.1.74:8088/plane-alert/pa_query.php?timestamp=.*&type=json` (Plane-Alert JSON endpoint; include at least one query parameter because docker-planefence requires it)
| `planeAlertFetchTimeout` | `15` (HTTP timeout in seconds; increase this if the browser works but the app times out)
| `planeAlertUserAgent` | `Mozilla/5.0 TrainDepartureDisplay/Plane-Alert` (HTTP User-Agent sent to the Plane-Alert web proxy)
| `planeAlertRefreshTime` | `30` (seconds between Plane-Alert background JSON refresh attempts)
| `planeAlertDisplayCount` | `5` (total Plane-Alert aircraft to show: the latest highlighted alert plus the remaining aircraft in the lower scrolling rows)
| `planeAlertMaxAgeHours` | `2` (maximum alert age in hours; set blank to show all Plane-Alert history)
| `planeAlertTopLeftTemplate` | `{summary_left}` (highlight row left block)
| `planeAlertTopRightTemplate` | `{summary_right}` (highlight row right block)
| `planeAlertScrollTemplate` | `{detail}` (single scrolling row block)
| `planeAlertNextLeftTemplate` | `{loop_alert}` (lower-row aircraft detail left block)
| `planeAlertNextRightTemplate` | `{loop_info}` (lower-row aircraft detail right block)

The Plane-Alert board sorts alerts newest first using the `timestamp` field, then mirrors the ADS-B layout as closely as the Plane-Alert data allows: callsign on the highlighted left block, tail/hex, equipment, and observed time on the highlighted right block, equipment/owner/position/time in the scrolling detail, and secondary rows with rank, callsign, and equipment on the left plus tail/hex and observed time on the right. Like ADS-B mode, the highlighted full-detail Plane-Alert record cycles through all displayed aircraft using a slightly extended `loopDepartureInterval`; the lower rows show the following records and then the configured `lastLineText` centered at the end of the list. The Plane-Alert board also labels the clock row with `Plane Alert`. Plane-Alert JSON is refreshed in the background and cached before/while the mode is displayed, so slow history queries do not block OLED animation or mode transitions. The app sends no-cache headers on Plane-Alert fetches and filters records older than `planeAlertMaxAgeHours` by default, so an all-history `planeAlertSourceUrl` does not keep showing stale morning alerts. The example `planeAlertSourceUrl` queries all timestamps; for large Plane-Alert histories, prefer a narrower docker-planefence regex query or increase `planeAlertFetchTimeout`.

Plane-Alert display templates use `{variable}` placeholders. Available variables are: `{summary_left}`, `{summary_right}`, `{summary}`, `{detail}`, `{loop_alert}`, `{loop_info}`, `{loop_time}`, `{position}`, `{position_ordinal}`, `{display_name}`, `{call}`, `{tail}`, `{tail_or_hex}`, `{hex}`, `{name}`, `{owner}`, `{equipment}`, `{aircraft_type}`, `{timestamp}`, `{time}`, `{date_time}`, `{latitude}`, and `{longitude}`.

Example custom Plane-Alert mode layout:

```bash
planeAlertTopLeftTemplate={display_name}
planeAlertTopRightTemplate={tail_or_hex} {aircraft_type} {time}
planeAlertScrollTemplate={equipment}  {name}  {latitude},{longitude}  {date_time}
planeAlertNextLeftTemplate={position_ordinal} {display_name} {aircraft_type}
planeAlertNextRightTemplate={tail_or_hex} {time}
```

## Plane-Alert MQTT alerts overlay (optional)

The `alerts` feature is separate from the Plane-Alert history board. It listens for Plane-Alert MQTT hit messages in a background MQTT network thread and interrupts whatever mode is currently visible with a full-screen alert. It does not poll Plane-Alert history, does not wait for MQTT during rendering, and does not consume a normal mode-rotation slot; include `alerts` in `transportModes` for readability alongside `train,adsb,plane-alert,alerts`.

| Key | Example Value
|-----|----------
| `alertsEnabled` | `True` (enables the interrupting MQTT alert overlay)
| `transportModes` | `train,adsb,plane-alert,alerts` (`alerts` is accepted as an interrupt-only feature and is not rotated like train/ADS-B/Plane-Alert boards)
| `alertsMqttHost` | `192.168.1.74` (MQTT broker hostname or IP address)
| `alertsMqttPort` | `1883` (MQTT broker port)
| `alertsMqttTopic` | `plane-alert/alerts/#` (Plane-Alert MQTT topic filter to subscribe to)
| `alertsMqttUsername` | `planealert` (optional MQTT username)
| `alertsMqttPassword` | `secret` (optional MQTT password)
| `alertsMqttClientId` | `train-departure-display-alerts` (MQTT client ID)
| `alertsMqttKeepalive` | `60` (MQTT keepalive seconds)
| `alertsMqttQos` | `0` (subscription QoS, clamped to `0`-`2`)
| `alertsMqttTlsEnabled` | `False` (enable broker TLS with default certificate validation)
| `alertsDisplayDuration` | `20` (seconds each MQTT alert remains full-screen unless replaced by a newer hit)
| `alertsTitleTemplate` | `{title}` (top full-screen alert row)
| `alertsTopTemplate` | `{headline}` (second alert row)
| `alertsMiddleTemplate` | `{equipment}  {name}` (third alert row)
| `alertsBottomTemplate` | `{detail}` (bottom scrolling alert row)

MQTT payloads can be JSON objects containing Plane-Alert-style fields such as `hex`, `tail`, `call`, `name`, `equipment`, `timestamp`, `lat`, and `lon`. Plain-text payloads are also accepted and can be displayed with `{raw}`. Alert templates support all Plane-Alert variables listed above plus `{title}`, `{headline}`, `{source}`, `{raw}`, and `{received_time}`. If multiple MQTT hits arrive while an alert is on screen, the newest queued hit replaces the active alert and restarts `alertsDisplayDuration`.

Example alert overlay configuration:

```bash
alertsEnabled=True
transportModes=train,adsb,plane-alert,alerts
alertsMqttHost=192.168.1.74
alertsMqttTopic=plane-alert/alerts/#
alertsDisplayDuration=25
alertsTitleTemplate={title}
alertsTopTemplate={display_name} {tail_or_hex} {time}
alertsMiddleTemplate={equipment}  {name}
alertsBottomTemplate={detail}  MQTT {source}
```

If using two screens the following line needs to be added into /boot/config.txt which is achieved by using the 'Define DT overlays' option within the Device configuration screen on balenaCloud: `spi1-3cs`

![](images/overlays.png)
