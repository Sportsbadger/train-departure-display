import os
import re


DEFAULT_ADSB_TOP_LEFT_TEMPLATE = "{summary_left}"
DEFAULT_ADSB_TOP_RIGHT_TEMPLATE = "{summary_right}"
DEFAULT_ADSB_SCROLL_TEMPLATE = "{detail}"
DEFAULT_ADSB_NEXT_LEFT_TEMPLATE = "{loop_aircraft}"
DEFAULT_ADSB_NEXT_RIGHT_TEMPLATE = "{loop_info}"

DEFAULT_PLANE_ALERT_TOP_LEFT_TEMPLATE = "{summary_left}"
DEFAULT_PLANE_ALERT_TOP_RIGHT_TEMPLATE = "{summary_right}"
DEFAULT_PLANE_ALERT_SCROLL_TEMPLATE = "{detail}"
DEFAULT_PLANE_ALERT_NEXT_LEFT_TEMPLATE = "{loop_alert}"
DEFAULT_PLANE_ALERT_NEXT_RIGHT_TEMPLATE = "{loop_info}"
DEFAULT_PLANE_ALERT_MAX_AGE_HOURS = 2.0

DEFAULT_ALERT_TITLE_TEMPLATE = "{title}"
DEFAULT_ALERT_TOP_TEMPLATE = "{headline}"
DEFAULT_ALERT_MIDDLE_TEMPLATE = "{equipment}  {name}"
DEFAULT_ALERT_BOTTOM_TEMPLATE = "{detail}"
DEFAULT_LAST_LINE_TEXT = "****Last Line****"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.upper() == "TRUE"


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    value = int(os.getenv(name) or default)
    if minimum is not None and value < minimum:
        return minimum
    return value


def _env_float(
    name: str,
    default: float,
    minimum: float | None = None,
) -> float:
    value = float(os.getenv(name) or default)
    if minimum is not None and value < minimum:
        return minimum
    return value


def _env_optional_float(
    name: str,
    default: float | None = None,
) -> float | None:
    value = os.getenv(name)
    if value is None:
        return default
    if value == "":
        return None
    return float(value)


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    return int(value)

# validate platform number
def parsePlatformData(platform):
    if platform is None:
        return ""
    elif bool(re.match(r'^(?:\d{1,2}[A-D]|[A-D]|\d{1,2})$', platform)):
        return platform
    else:
        return ""

def loadConfig():
    data = {
        "journey": {},
        "api": {},
        "transport": {},
        "adsb": {},
        "planeAlert": {},
        "alerts": {},
    }

    data["targetFPS"] = int(os.getenv("targetFPS") or 70)
    data["refreshTime"] = int(os.getenv("refreshTime") or 180)
    data["fpsTime"] = int(os.getenv("fpsTime") or 180)
    data["screenRotation"] = int(os.getenv("screenRotation") or 2)
    data["screenBlankHours"] = os.getenv("screenBlankHours") or ""
    data["headless"] = False
    if os.getenv("headless", "").upper() == "TRUE":
        data["headless"] = True

    data["debug"] = False
    if os.getenv("debug", "").upper() == "TRUE":
        data["debug"] = True
    else:
        if os.getenv("debug") and os.getenv("debug").isnumeric():
            data["debug"] = int(os.getenv("debug"))

    data["dualScreen"] = False
    if os.getenv("dualScreen", "").upper() == "TRUE":
        data["dualScreen"] = True
    data["firstDepartureBold"] = True
    if os.getenv("firstDepartureBold", "").upper() == "FALSE":
        data["firstDepartureBold"] = False
    data["hoursPattern"] = re.compile("^((2[0-3]|[0-1]?[0-9])-(2[0-3]|[0-1]?[0-9]))$")

    data["journey"]["departureStation"] = os.getenv("departureStation") or "PAD"

    data["journey"]["destinationStation"] = os.getenv("destinationStation") or ""
    if data["journey"]["destinationStation"] == "null" or data["journey"]["destinationStation"] == "undefined":
        data["journey"]["destinationStation"] = ""

    data["journey"]["individualStationDepartureTime"] = False
    if os.getenv("individualStationDepartureTime", "").upper() == "TRUE":
        data["journey"]["individualStationDepartureTime"] = True

    data["journey"]["outOfHoursName"] = os.getenv("outOfHoursName") or "London Paddington"
    data["journey"]["stationAbbr"] = {"International": "Intl."}
    data["journey"]['timeOffset'] = os.getenv("timeOffset") or "0"
    data["journey"]["screen1Platform"] = parsePlatformData(os.getenv("screen1Platform"))
    data["journey"]["screen2Platform"] = parsePlatformData(os.getenv("screen2Platform"))

    data["api"]["apiKey"] = os.getenv("apiKey") or None
    data["api"]["operatingHours"] = os.getenv("operatingHours") or ""

    data["showDepartureNumbers"] = False
    if os.getenv("showDepartureNumbers", "").upper() == "TRUE":
        data["showDepartureNumbers"] = True

    data["loopDepartureCount"] = int(os.getenv("loopDepartureCount") or 2)
    if data["loopDepartureCount"] < 2:
        data["loopDepartureCount"] = 2

    data["loopDepartureInterval"] = int(os.getenv("loopDepartureInterval") or 10)
    if data["loopDepartureInterval"] < 1:
        data["loopDepartureInterval"] = 1

    data["adsb"]["enabled"] = _env_bool("adsbEnabled", False)
    data["adsb"]["sourceUrl"] = (
        os.getenv("adsbSourceUrl")
        or "http://192.168.1.74/readsb/data/aircraft.json"
    )
    data["adsb"]["userAgent"] = (
        os.getenv("adsbUserAgent")
        or "Mozilla/5.0 TrainDepartureDisplay/ADS-B"
    )
    data["adsb"]["fetchTimeout"] = _env_float(
        "adsbFetchTimeout",
        2.0,
        minimum=0.1,
    )
    data["adsb"]["refreshTime"] = _env_int("adsbRefreshTime", 10, minimum=1)
    data["adsb"]["displayCount"] = _env_int("adsbDisplayCount", 5, minimum=1)
    data["adsb"]["homeLat"] = _env_optional_float("adsbHomeLat")
    data["adsb"]["homeLon"] = _env_optional_float("adsbHomeLon")
    data["adsb"]["maxAgeSeconds"] = _env_float(
        "adsbMaxAgeSeconds",
        30.0,
        minimum=0.0,
    )
    data["adsb"]["maxDistanceNm"] = _env_optional_float("adsbMaxDistanceNm")
    data["adsb"]["minAltitudeFt"] = _env_optional_int("adsbMinAltitudeFt")
    data["adsb"]["routeLookupEnabled"] = _env_bool(
        "adsbRouteLookupEnabled",
        False,
    )
    data["adsb"]["routeApiUrl"] = (
        os.getenv("adsbRouteApiUrl")
        or "https://api.adsb.lol/api/0/routeset"
    )
    data["adsb"]["routeFetchTimeout"] = _env_float(
        "adsbRouteFetchTimeout",
        4.0,
        minimum=0.1,
    )
    data["adsb"]["routeDisplay"] = (
        os.getenv("adsbRouteDisplay") or "iata"
    ).lower()
    if data["adsb"]["routeDisplay"] not in ("iata", "icao", "city"):
        data["adsb"]["routeDisplay"] = "iata"

    data["adsb"]["topLeftTemplate"] = (
        os.getenv("adsbTopLeftTemplate") or DEFAULT_ADSB_TOP_LEFT_TEMPLATE
    )
    data["adsb"]["topRightTemplate"] = (
        os.getenv("adsbTopRightTemplate") or DEFAULT_ADSB_TOP_RIGHT_TEMPLATE
    )
    data["adsb"]["scrollTemplate"] = (
        os.getenv("adsbScrollTemplate") or DEFAULT_ADSB_SCROLL_TEMPLATE
    )
    data["adsb"]["nextLeftTemplate"] = (
        os.getenv("adsbNextLeftTemplate") or DEFAULT_ADSB_NEXT_LEFT_TEMPLATE
    )
    data["adsb"]["nextRightTemplate"] = (
        os.getenv("adsbNextRightTemplate") or DEFAULT_ADSB_NEXT_RIGHT_TEMPLATE
    )

    data["planeAlert"]["enabled"] = _env_bool("planeAlertEnabled", False)
    data["planeAlert"]["sourceUrl"] = (
        os.getenv("planeAlertSourceUrl")
        or "http://192.168.1.74:8088/plane-alert/pa_query.php?timestamp=.*&type=json"
    )
    data["planeAlert"]["userAgent"] = (
        os.getenv("planeAlertUserAgent")
        or "Mozilla/5.0 TrainDepartureDisplay/Plane-Alert"
    )
    data["planeAlert"]["fetchTimeout"] = _env_float(
        "planeAlertFetchTimeout",
        15.0,
        minimum=0.1,
    )
    data["planeAlert"]["refreshTime"] = _env_int(
        "planeAlertRefreshTime",
        30,
        minimum=1,
    )
    data["planeAlert"]["displayCount"] = _env_int(
        "planeAlertDisplayCount",
        5,
        minimum=1,
    )
    data["planeAlert"]["maxAgeHours"] = _env_optional_float(
        "planeAlertMaxAgeHours",
        DEFAULT_PLANE_ALERT_MAX_AGE_HOURS,
    )
    data["planeAlert"]["topLeftTemplate"] = (
        os.getenv("planeAlertTopLeftTemplate")
        or DEFAULT_PLANE_ALERT_TOP_LEFT_TEMPLATE
    )
    data["planeAlert"]["topRightTemplate"] = (
        os.getenv("planeAlertTopRightTemplate")
        or DEFAULT_PLANE_ALERT_TOP_RIGHT_TEMPLATE
    )
    data["planeAlert"]["scrollTemplate"] = (
        os.getenv("planeAlertScrollTemplate")
        or DEFAULT_PLANE_ALERT_SCROLL_TEMPLATE
    )
    data["planeAlert"]["nextLeftTemplate"] = (
        os.getenv("planeAlertNextLeftTemplate")
        or DEFAULT_PLANE_ALERT_NEXT_LEFT_TEMPLATE
    )
    data["planeAlert"]["nextRightTemplate"] = (
        os.getenv("planeAlertNextRightTemplate")
        or DEFAULT_PLANE_ALERT_NEXT_RIGHT_TEMPLATE
    )

    data["alerts"]["enabled"] = _env_bool("alertsEnabled", False)
    data["alerts"]["mqttHost"] = os.getenv("alertsMqttHost") or "127.0.0.1"
    data["alerts"]["mqttPort"] = _env_int("alertsMqttPort", 1883, minimum=1)
    data["alerts"]["mqttTopic"] = (
        os.getenv("alertsMqttTopic") or "plane-alert/alerts/#"
    )
    data["alerts"]["mqttUsername"] = os.getenv("alertsMqttUsername") or ""
    data["alerts"]["mqttPassword"] = os.getenv("alertsMqttPassword") or ""
    data["alerts"]["mqttClientId"] = (
        os.getenv("alertsMqttClientId") or "train-departure-display-alerts"
    )
    data["alerts"]["mqttKeepalive"] = _env_int(
        "alertsMqttKeepalive",
        60,
        minimum=1,
    )
    data["alerts"]["mqttQos"] = _env_int("alertsMqttQos", 0, minimum=0)
    if data["alerts"]["mqttQos"] > 2:
        data["alerts"]["mqttQos"] = 2
    data["alerts"]["mqttTlsEnabled"] = _env_bool("alertsMqttTlsEnabled", False)
    data["alerts"]["displayDuration"] = _env_float(
        "alertsDisplayDuration",
        20.0,
        minimum=1.0,
    )
    data["alerts"]["titleTemplate"] = (
        os.getenv("alertsTitleTemplate") or DEFAULT_ALERT_TITLE_TEMPLATE
    )
    data["alerts"]["topTemplate"] = (
        os.getenv("alertsTopTemplate") or DEFAULT_ALERT_TOP_TEMPLATE
    )
    data["alerts"]["middleTemplate"] = (
        os.getenv("alertsMiddleTemplate") or DEFAULT_ALERT_MIDDLE_TEMPLATE
    )
    data["alerts"]["bottomTemplate"] = (
        os.getenv("alertsBottomTemplate") or DEFAULT_ALERT_BOTTOM_TEMPLATE
    )

    data["transport"]["modes"] = os.getenv("transportModes") or "train"
    data["transport"]["lastLineText"] = (
        os.getenv("lastLineText") or DEFAULT_LAST_LINE_TEXT
    )
    data["transport"]["modeSwitchInterval"] = _env_int(
        "modeSwitchInterval",
        300,
        minimum=1,
    )
    data["transport"]["fallbackMode"] = (
        os.getenv("transportFallbackMode") or "train"
    ).lower()

    return data
