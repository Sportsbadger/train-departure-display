import os
import re
from typing import Any


def parse_int_env(name: str, default: int, minimum: int | None = None) -> int:
    """Parse an integer environment variable with an optional minimum."""
    value = int(os.getenv(name) or default)
    if minimum is not None and value < minimum:
        return minimum
    return value


def parse_float_env(
    name: str,
    default: float | None = None,
    minimum: float | None = None,
) -> float | None:
    """Parse a float environment variable with an optional minimum."""
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    value = float(raw_value)
    if minimum is not None and value < minimum:
        return minimum
    return value


# validate platform number
def parsePlatformData(platform):
    if platform is None:
        return ""
    elif bool(re.match(r'^(?:\d{1,2}[A-D]|[A-D]|\d{1,2})$', platform)):
        return platform
    else:
        return ""


def loadConfig() -> dict[str, Any]:
    data = {
        "journey": {},
        "api": {}
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

    data["adsb"] = {
        "sourceType": os.getenv("adsbSourceType") or "readsb-json",
        "jsonUrl": os.getenv("adsbJsonUrl") or "",
        "host": os.getenv("adsbHost") or "",
        "jsonPort": parse_int_env("adsbJsonPort", 80, minimum=1),
        "jsonPath": os.getenv("adsbJsonPath") or "/tar1090/data/aircraft.json",
        "receiverLat": parse_float_env("adsbReceiverLat"),
        "receiverLon": parse_float_env("adsbReceiverLon"),
        "refreshTime": parse_int_env("adsbRefreshTime", 5, minimum=1),
        "maxAircraft": parse_int_env("adsbMaxAircraft", 8, minimum=1),
        "maxAge": parse_int_env("adsbMaxAge", 30, minimum=1),
        "maxDistanceNm": parse_float_env("adsbMaxDistanceNm", minimum=0.0),
        "minAltitude": parse_int_env("adsbMinAltitude", 0, minimum=0)
        if os.getenv("adsbMinAltitude") not in (None, "") else None,
        "maxAltitude": parse_int_env("adsbMaxAltitude", 60000, minimum=0)
        if os.getenv("adsbMaxAltitude") not in (None, "") else None,
        "connectTimeout": parse_float_env("adsbConnectTimeout", 1.0, minimum=0.1),
        "readTimeout": parse_float_env("adsbReadTimeout", 1.0, minimum=0.1),
        "beastHost": os.getenv("adsbBeastHost") or "",
        "beastPort": parse_int_env("adsbBeastPort", 30005, minimum=1),
    }

    return data
