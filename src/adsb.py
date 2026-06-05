from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Iterable, Mapping

EARTH_RADIUS_NM = 3440.065
COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


@dataclass(frozen=True)
class ReceiverPosition:
    """Geographic position of the ADS-B receiver."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class Aircraft:
    """Decoded aircraft details needed by the display."""

    hex_ident: str
    callsign: str
    latitude: float | None
    longitude: float | None
    altitude_ft: int | None
    ground_speed_kt: int | None
    track_deg: int | None
    vertical_rate_fpm: int | None
    squawk: str
    seen_s: float
    distance_nm: float | None = None
    bearing_deg: float | None = None


@dataclass(frozen=True)
class DisplayAircraft:
    """Aircraft plus display-specific distance and bearing fields."""

    aircraft: Aircraft
    distance_nm: float
    bearing_deg: float
    bearing_label: str


def parse_aircraft_payload(payload: Mapping[str, Any]) -> list[Aircraft]:
    """Parse a readsb/tar1090 aircraft JSON payload.

    Args:
        payload: Decoded JSON mapping containing an ``aircraft`` list.

    Returns:
        Parsed aircraft records. Invalid records are skipped.

    Raises:
        ValueError: If the payload shape is not a readsb-style aircraft object.
    """
    raw_aircraft = payload.get("aircraft")
    if not isinstance(raw_aircraft, list):
        raise ValueError("ADS-B payload must contain an aircraft list")

    aircraft: list[Aircraft] = []
    for item in raw_aircraft:
        if not isinstance(item, Mapping):
            continue
        parsed = parse_aircraft(item)
        if parsed is not None:
            aircraft.append(parsed)
    return aircraft


def parse_aircraft(item: Mapping[str, Any]) -> Aircraft | None:
    """Parse one readsb/tar1090 aircraft entry.

    Args:
        item: Raw aircraft mapping from readsb/tar1090 JSON.

    Returns:
        Aircraft if the minimum identity fields are present, otherwise ``None``.
    """
    hex_ident = clean_text(item.get("hex"))
    if not hex_ident:
        return None

    callsign = clean_text(item.get("flight")) or hex_ident.upper()
    seen_s = parse_float(item.get("seen"))
    if seen_s is None:
        seen_s = parse_float(item.get("seen_pos")) or 0.0

    return Aircraft(
        hex_ident=hex_ident.upper(),
        callsign=callsign.upper(),
        latitude=parse_float(item.get("lat")),
        longitude=parse_float(item.get("lon")),
        altitude_ft=parse_altitude(item.get("alt_baro")),
        ground_speed_kt=parse_int(item.get("gs")),
        track_deg=parse_int(item.get("track")),
        vertical_rate_fpm=parse_int(item.get("baro_rate")),
        squawk=clean_text(item.get("squawk")),
        seen_s=seen_s,
    )


def prepare_display_aircraft(
    aircraft: Iterable[Aircraft],
    receiver: ReceiverPosition,
    max_age_s: float,
    max_aircraft: int,
    max_distance_nm: float | None = None,
    min_altitude_ft: int | None = None,
    max_altitude_ft: int | None = None,
) -> list[DisplayAircraft]:
    """Filter aircraft and sort them nearest-first for display.

    Args:
        aircraft: Parsed aircraft records.
        receiver: Receiver position used for distance/bearing calculations.
        max_age_s: Maximum accepted age from the decoded feed.
        max_aircraft: Maximum number of aircraft to return.
        max_distance_nm: Optional maximum display distance.
        min_altitude_ft: Optional minimum altitude filter.
        max_altitude_ft: Optional maximum altitude filter.

    Returns:
        Nearest aircraft ready for display.
    """
    display_items: list[DisplayAircraft] = []
    for item in aircraft:
        if item.seen_s > max_age_s:
            continue
        if item.latitude is None or item.longitude is None:
            continue
        if not altitude_in_range(item.altitude_ft, min_altitude_ft, max_altitude_ft):
            continue

        distance_nm = haversine_nm(
            receiver.latitude,
            receiver.longitude,
            item.latitude,
            item.longitude,
        )
        if max_distance_nm is not None and distance_nm > max_distance_nm:
            continue

        bearing_deg = initial_bearing_deg(
            receiver.latitude,
            receiver.longitude,
            item.latitude,
            item.longitude,
        )
        display_items.append(
            DisplayAircraft(
                aircraft=item,
                distance_nm=distance_nm,
                bearing_deg=bearing_deg,
                bearing_label=compass_label(bearing_deg),
            )
        )

    display_items.sort(key=lambda item: item.distance_nm)
    return display_items[:max(0, max_aircraft)]


def format_aircraft_primary(item: DisplayAircraft) -> str:
    """Format an aircraft primary display row."""
    distance = f"{item.distance_nm:.0f}nm"
    altitude = format_altitude(item.aircraft.altitude_ft)
    return "  ".join(
        part for part in (
            item.aircraft.callsign,
            distance,
            item.bearing_label,
            altitude,
        ) if part
    )


def format_aircraft_secondary(item: DisplayAircraft) -> str:
    """Format an aircraft secondary display row."""
    speed = format_speed(item.aircraft.ground_speed_kt)
    heading = format_heading(item.aircraft.track_deg)
    vertical = format_vertical_rate(item.aircraft.vertical_rate_fpm)
    squawk = f"Sq {item.aircraft.squawk}" if item.aircraft.squawk else ""
    return "  ".join(part for part in (speed, heading, vertical, squawk) if part)


def altitude_in_range(
    altitude_ft: int | None,
    min_altitude_ft: int | None,
    max_altitude_ft: int | None,
) -> bool:
    """Return whether altitude satisfies optional display filters."""
    if altitude_ft is None:
        return True
    if min_altitude_ft is not None and altitude_ft < min_altitude_ft:
        return False
    if max_altitude_ft is not None and altitude_ft > max_altitude_ft:
        return False
    return True


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in nautical miles."""
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return initial bearing in degrees from point one to point two."""
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lon = radians(lon2 - lon1)

    x = sin(delta_lon) * cos(lat2_rad)
    y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(delta_lon)
    return (atan2(x, y) * 180 / 3.141592653589793 + 360) % 360


def compass_label(bearing_deg: float) -> str:
    """Return an eight-point compass label for a bearing."""
    index = int((bearing_deg + 22.5) // 45) % len(COMPASS_POINTS)
    return COMPASS_POINTS[index]


def format_altitude(altitude_ft: int | None) -> str:
    """Format altitude for the OLED display."""
    if altitude_ft is None:
        return ""
    if altitude_ft >= 10000:
        return f"{round(altitude_ft / 1000):.0f}k ft"
    return f"{altitude_ft}ft"


def format_speed(speed_kt: int | None) -> str:
    """Format ground speed for the OLED display."""
    if speed_kt is None:
        return ""
    return f"{speed_kt}kt"


def format_heading(track_deg: int | None) -> str:
    """Format track heading for the OLED display."""
    if track_deg is None:
        return ""
    return f"Hdg {track_deg:03d}"


def format_vertical_rate(vertical_rate_fpm: int | None) -> str:
    """Format climb/descent rate for the OLED display."""
    if vertical_rate_fpm is None or vertical_rate_fpm == 0:
        return ""
    arrow = "↑" if vertical_rate_fpm > 0 else "↓"
    return f"{arrow}{abs(vertical_rate_fpm)}"


def clean_text(value: Any) -> str:
    """Return stripped text for feed values."""
    if value is None:
        return ""
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    """Parse a float value from decoded ADS-B JSON."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    """Parse an integer value from decoded ADS-B JSON."""
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def parse_altitude(value: Any) -> int | None:
    """Parse barometric altitude, ignoring ground/non-numeric markers."""
    if isinstance(value, str) and value.lower() == "ground":
        return 0
    return parse_int(value)
