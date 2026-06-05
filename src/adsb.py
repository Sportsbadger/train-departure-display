"""ADS-B aircraft parsing and display preparation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, radians, sin, sqrt
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
    """Decoded aircraft fields needed by the display.

    Attributes:
        hex_ident: ICAO hex identifier.
        callsign: Callsign/flight, falling back to the hex identifier.
        latitude: Aircraft latitude, if available.
        longitude: Aircraft longitude, if available.
        altitude_ft: Barometric altitude in feet, if airborne and available.
        ground_speed_kt: Ground speed in knots, if available.
        track_deg: Ground track in degrees, if available.
        vertical_rate_fpm: Vertical rate in feet per minute, if available.
        squawk: Transponder squawk code, if available.
        seen_s: Seconds since the feeder last saw this aircraft.
    """

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


@dataclass(frozen=True)
class DisplayAircraft:
    """Aircraft enriched with receiver-relative display fields."""

    aircraft: Aircraft
    distance_nm: float
    bearing_deg: float
    bearing_label: str


def parse_aircraft_payload(payload: Mapping[str, Any]) -> list[Aircraft]:
    """Parse a readsb/tar1090 aircraft JSON payload.

    Args:
        payload: Decoded JSON object containing an ``aircraft`` list.

    Returns:
        Parsed aircraft records. Invalid aircraft entries are skipped.

    Raises:
        ValueError: If the payload does not contain a readsb-style aircraft list.
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
        An aircraft record when identity is present, otherwise ``None``.
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
        max_age_s: Maximum accepted aircraft age in seconds.
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
        if not altitude_in_range(
            item.altitude_ft,
            min_altitude_ft,
            max_altitude_ft,
        ):
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
    """Format an aircraft primary row for a small OLED display.

    Args:
        item: Display aircraft record.

    Returns:
        Compact primary row text.
    """
    distance = f"{item.distance_nm:.0f}nm"
    altitude = format_altitude(item.aircraft.altitude_ft)
    return "  ".join(
        part
        for part in (
            item.aircraft.callsign,
            distance,
            item.bearing_label,
            altitude,
        )
        if part
    )


def format_aircraft_secondary(item: DisplayAircraft) -> str:
    """Format an aircraft secondary row for a small OLED display.

    Args:
        item: Display aircraft record.

    Returns:
        Compact secondary row text.
    """
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
    """Return whether altitude satisfies optional display filters.

    Args:
        altitude_ft: Aircraft altitude.
        min_altitude_ft: Optional minimum altitude.
        max_altitude_ft: Optional maximum altitude.

    Returns:
        ``True`` when the altitude is accepted.
    """
    if altitude_ft is None:
        return min_altitude_ft is None and max_altitude_ft is None
    if min_altitude_ft is not None and altitude_ft < min_altitude_ft:
        return False
    if max_altitude_ft is not None and altitude_ft > max_altitude_ft:
        return False
    return True


def haversine_nm(
    origin_lat: float,
    origin_lon: float,
    target_lat: float,
    target_lon: float,
) -> float:
    """Calculate great-circle distance in nautical miles.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        target_lat: Target latitude.
        target_lon: Target longitude.

    Returns:
        Distance in nautical miles.
    """
    lat_1 = radians(origin_lat)
    lat_2 = radians(target_lat)
    delta_lat = radians(target_lat - origin_lat)
    delta_lon = radians(target_lon - origin_lon)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat_1) * cos(lat_2) * sin(delta_lon / 2) ** 2
    )
    return EARTH_RADIUS_NM * 2 * atan2(sqrt(a), sqrt(1 - a))


def initial_bearing_deg(
    origin_lat: float,
    origin_lon: float,
    target_lat: float,
    target_lon: float,
) -> float:
    """Calculate initial bearing from origin to target.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        target_lat: Target latitude.
        target_lon: Target longitude.

    Returns:
        Initial bearing in degrees from north.
    """
    lat_1 = radians(origin_lat)
    lat_2 = radians(target_lat)
    delta_lon = radians(target_lon - origin_lon)

    x_value = sin(delta_lon) * cos(lat_2)
    y_value = cos(lat_1) * sin(lat_2) - sin(lat_1) * cos(lat_2) * cos(delta_lon)
    return (degrees(atan2(x_value, y_value)) + 360) % 360


def compass_label(bearing_deg: float) -> str:
    """Convert bearing degrees to an eight-point compass label.

    Args:
        bearing_deg: Bearing in degrees.

    Returns:
        Compass label such as ``N`` or ``SW``.
    """
    index = int((bearing_deg + 22.5) // 45) % len(COMPASS_POINTS)
    return COMPASS_POINTS[index]


def clean_text(value: Any) -> str:
    """Return normalized text from a JSON value.

    Args:
        value: Raw JSON value.

    Returns:
        Stripped text, or an empty string for missing/non-text values.
    """
    if value is None:
        return ""
    return str(value).strip()


def parse_float(value: Any) -> float | None:
    """Parse a float from a JSON value.

    Args:
        value: Raw JSON value.

    Returns:
        Parsed float, or ``None`` when unavailable/invalid.
    """
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    """Parse a rounded integer from a JSON value.

    Args:
        value: Raw JSON value.

    Returns:
        Parsed integer, or ``None`` when unavailable/invalid.
    """
    parsed = parse_float(value)
    if parsed is None:
        return None
    return round(parsed)


def parse_altitude(value: Any) -> int | None:
    """Parse an altitude value from readsb/tar1090 JSON.

    Args:
        value: Raw altitude value.

    Returns:
        Altitude in feet, or ``None`` for ground/invalid/missing values.
    """
    if isinstance(value, str) and value.lower() == "ground":
        return None
    return parse_int(value)


def format_altitude(altitude_ft: int | None) -> str:
    """Format altitude for compact display.

    Args:
        altitude_ft: Altitude in feet.

    Returns:
        Compact altitude text.
    """
    if altitude_ft is None:
        return ""
    if abs(altitude_ft) >= 10_000:
        return f"{altitude_ft / 1000:.0f}k ft"
    return f"{altitude_ft}ft"


def format_speed(speed_kt: int | None) -> str:
    """Format speed for compact display.

    Args:
        speed_kt: Ground speed in knots.

    Returns:
        Compact speed text.
    """
    if speed_kt is None:
        return ""
    return f"{speed_kt}kt"


def format_heading(track_deg: int | None) -> str:
    """Format heading for compact display.

    Args:
        track_deg: Track in degrees.

    Returns:
        Compact heading text.
    """
    if track_deg is None:
        return ""
    return f"Hdg {track_deg % 360}"


def format_vertical_rate(vertical_rate_fpm: int | None) -> str:
    """Format vertical rate for compact display.

    Args:
        vertical_rate_fpm: Vertical rate in feet per minute.

    Returns:
        Compact climb/descent text.
    """
    if vertical_rate_fpm is None or vertical_rate_fpm == 0:
        return ""
    arrow = "↑" if vertical_rate_fpm > 0 else "↓"
    return f"{arrow}{abs(vertical_rate_fpm)}"
