import os
import re


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.upper() == "TRUE"


def parse_float(value: str | None, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value: str | None, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        "adsb": {},
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

    data["modeSwitchInterval"] = parse_int(os.getenv("modeSwitchInterval"), 300)
    if data["modeSwitchInterval"] < 60:
        data["modeSwitchInterval"] = 60

    data["adsb"]["enabled"] = parse_bool(os.getenv("adsbEnabled"), False)
    data["adsb"]["host"] = os.getenv("adsbHost") or "127.0.0.1"
    data["adsb"]["port"] = parse_int(os.getenv("adsbPort"), 30005)
    data["adsb"]["receiverLatitude"] = parse_float(os.getenv("adsbReceiverLatitude"))
    data["adsb"]["receiverLongitude"] = parse_float(os.getenv("adsbReceiverLongitude"))
    data["adsb"]["readTimeout"] = parse_float(os.getenv("adsbReadTimeout"), 2.0)
    data["adsb"]["maxAircraftAge"] = parse_int(os.getenv("adsbMaxAircraftAge"), 300)
    data["adsb"]["maxPlanes"] = parse_int(os.getenv("adsbMaxPlanes"), 6)
    if data["adsb"]["maxPlanes"] < 1:
        data["adsb"]["maxPlanes"] = 1

    if data["adsb"]["enabled"] and (
        data["adsb"]["receiverLatitude"] is None
        or data["adsb"]["receiverLongitude"] is None
    ):
        raise ValueError(
            "Please configure adsbReceiverLatitude and adsbReceiverLongitude "
            "when adsbEnabled=True"
        )

    return data
