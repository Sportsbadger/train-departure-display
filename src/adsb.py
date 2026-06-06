from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Mapping

import requests

EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True)
class AdsbAircraft:
    """Display-ready aircraft data from readsb/tar1090 JSON."""

    hex: str
    flight: str
    distance_nm: float
    bearing_deg: int
    altitude_ft: int | None
    ground_speed_kt: int | None
    track_deg: int | None
    vertical_rate_fpm: int | None
    squawk: str
    aircraft_type: str
    registration: str
    seen_seconds: float

    @property
    def display_name(self) -> str:
        """Return the preferred aircraft label for display."""
        if self.flight:
            return self.flight
        if self.registration:
            return self.registration
        return self.hex.upper()


class AdsbDataError(ValueError):
    """Raised when ADS-B data cannot be parsed or validated."""


def fetch_aircraft_json(
    source_url: str,
    timeout_s: float,
    user_agent: str,
) -> Mapping[str, Any]:
    """Fetch aircraft JSON from a readsb/tar1090 endpoint.

    Args:
        source_url: HTTP URL for the readsb/tar1090 aircraft.json file.
        timeout_s: Maximum request time in seconds.
        user_agent: HTTP User-Agent header for reverse proxies.

    Returns:
        Decoded JSON mapping.

    Raises:
        requests.RequestException: If the HTTP request fails or times out.
        AdsbDataError: If the response is not a JSON object.
    """
    headers = {"User-Agent": user_agent}
    response = requests.get(source_url, headers=headers, timeout=timeout_s)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise AdsbDataError("ADS-B response must be a JSON object")
    return payload


def parse_aircraft(
    payload: Mapping[str, Any],
    home_lat: float,
    home_lon: float,
    max_age_s: float,
    max_distance_nm: float | None,
    min_altitude_ft: int | None,
    limit: int,
) -> list[AdsbAircraft]:
    """Parse, filter, and sort ADS-B aircraft by distance.

    Args:
        payload: Decoded readsb/tar1090 aircraft.json payload.
        home_lat: Receiver/display latitude in decimal degrees.
        home_lon: Receiver/display longitude in decimal degrees.
        max_age_s: Maximum accepted ``seen`` age in seconds.
        max_distance_nm: Optional maximum distance in nautical miles.
        min_altitude_ft: Optional minimum altitude in feet.
        limit: Maximum number of aircraft to return.

    Returns:
        Nearest matching aircraft.

    Raises:
        AdsbDataError: If the payload does not contain an aircraft list.
    """
    aircraft_items = payload.get("aircraft")
    if not isinstance(aircraft_items, list):
        raise AdsbDataError("ADS-B response must contain an aircraft list")

    aircraft = [
        parsed
        for item in aircraft_items
        if isinstance(item, Mapping)
        for parsed in [_parse_aircraft_item(item, home_lat, home_lon)]
        if parsed is not None
    ]

    filtered = [
        item
        for item in aircraft
        if _passes_filters(item, max_age_s, max_distance_nm, min_altitude_ft)
    ]
    return sorted(filtered, key=lambda item: item.distance_nm)[:limit]


def format_altitude(altitude_ft: int | None) -> str:
    """Format altitude for the compact display."""
    if altitude_ft is None:
        return "----ft"
    if altitude_ft == 0:
        return "Ground"
    return f"{altitude_ft}ft"


def format_speed(speed_kt: int | None) -> str:
    """Format ground speed for the compact display."""
    if speed_kt is None:
        return "---kt"
    return f"{speed_kt}kt"


def format_vertical_rate(vertical_rate_fpm: int | None) -> str:
    """Format vertical rate with an arrow-like prefix for OLED fonts."""
    if vertical_rate_fpm is None or vertical_rate_fpm == 0:
        return "level"
    if vertical_rate_fpm > 0:
        return f"climb {vertical_rate_fpm}fpm"
    return f"desc {abs(vertical_rate_fpm)}fpm"


def format_heading(degrees: int | None) -> str:
    """Format track heading with compass point and degrees."""
    if degrees is None:
        return "trk ---"
    return f"{_compass_point(degrees)} {degrees:03d}"


def build_detail_text(aircraft: AdsbAircraft) -> str:
    """Build the scrolling detail line for an aircraft."""
    parts = [
        aircraft.aircraft_type,
        aircraft.registration,
        format_heading(aircraft.track_deg),
        format_speed(aircraft.ground_speed_kt),
        format_vertical_rate(aircraft.vertical_rate_fpm),
    ]
    if aircraft.squawk:
        parts.append(f"sq {aircraft.squawk}")
    return "  ".join(part for part in parts if part)


def _parse_aircraft_item(
    item: Mapping[str, Any],
    home_lat: float,
    home_lon: float,
) -> AdsbAircraft | None:
    lat = _optional_float(item.get("lat"))
    lon = _optional_float(item.get("lon"))
    if lat is None or lon is None:
        return None

    hex_value = _clean_text(item.get("hex"))
    if not hex_value:
        return None

    distance_nm = distance_between_nm(home_lat, home_lon, lat, lon)
    bearing_deg = bearing_between_deg(home_lat, home_lon, lat, lon)

    return AdsbAircraft(
        hex=hex_value,
        flight=_clean_text(item.get("flight")),
        distance_nm=distance_nm,
        bearing_deg=bearing_deg,
        altitude_ft=_parse_altitude(item.get("alt_baro", item.get("alt_geom"))),
        ground_speed_kt=_optional_int(item.get("gs")),
        track_deg=_optional_int(item.get("track")),
        vertical_rate_fpm=_optional_int(item.get("baro_rate", item.get("geom_rate"))),
        squawk=_clean_text(item.get("squawk")),
        aircraft_type=_clean_text(item.get("t")),
        registration=_clean_text(item.get("r")),
        seen_seconds=_optional_float(item.get("seen")) or 0.0,
    )


def _passes_filters(
    aircraft: AdsbAircraft,
    max_age_s: float,
    max_distance_nm: float | None,
    min_altitude_ft: int | None,
) -> bool:
    if aircraft.seen_seconds > max_age_s:
        return False
    if max_distance_nm is not None and aircraft.distance_nm > max_distance_nm:
        return False
    if min_altitude_ft is None:
        return True
    if aircraft.altitude_ft is None:
        return False
    return aircraft.altitude_ft >= min_altitude_ft


def distance_between_nm(
    origin_lat: float,
    origin_lon: float,
    target_lat: float,
    target_lon: float,
) -> float:
    """Calculate great-circle distance between coordinates in nautical miles."""
    lat1 = radians(origin_lat)
    lon1 = radians(origin_lon)
    lat2 = radians(target_lat)
    lon2 = radians(target_lon)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return EARTH_RADIUS_NM * 2 * atan2(sqrt(haversine), sqrt(1 - haversine))


def bearing_between_deg(
    origin_lat: float,
    origin_lon: float,
    target_lat: float,
    target_lon: float,
) -> int:
    """Calculate initial bearing from origin to target in degrees."""
    lat1 = radians(origin_lat)
    lat2 = radians(target_lat)
    delta_lon = radians(target_lon - origin_lon)

    y = sin(delta_lon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)
    return int(round((atan2(y, x) * 180 / 3.141592653589793 + 360) % 360))


def _parse_altitude(value: Any) -> int | None:
    if value == "ground":
        return 0
    return _optional_int(value)


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _compass_point(degrees: int) -> str:
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return points[int((degrees % 360 + 22.5) // 45) % len(points)]
