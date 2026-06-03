from __future__ import annotations

import math
import socket
import time
from dataclasses import dataclass
from typing import Iterable

BEAST_ESCAPE = 0x1A
EARTH_RADIUS_NM = 3440.065
CPR_SCALE = 131072.0


@dataclass(frozen=True)
class ReceiverLocation:
    """Configured ADS-B receiver location."""

    latitude: float
    longitude: float


@dataclass
class Plane:
    """Current display state for one aircraft."""

    icao: str
    callsign: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_ft: int | None = None
    ground_speed_kt: int | None = None
    track_deg: int | None = None
    vertical_rate_fpm: int | None = None
    distance_nm: float | None = None
    last_seen: float = 0.0


@dataclass(frozen=True)
class BeastFrame:
    """Decoded Beast binary payload."""

    frame_type: str
    payload: bytes


@dataclass(frozen=True)
class CprPosition:
    """Compact Position Reporting value from an ADS-B position message."""

    latitude: int
    longitude: int
    odd: bool
    timestamp: float


@dataclass
class AircraftState:
    """Internal tracked ADS-B state for one ICAO address."""

    plane: Plane
    even_cpr: CprPosition | None = None
    odd_cpr: CprPosition | None = None


class AdsbClient:
    """Read Beast-format ADS-B data and maintain nearby aircraft state."""

    def __init__(
        self,
        host: str,
        port: int,
        receiver_location: ReceiverLocation,
        timeout_s: float,
        max_age_s: float,
    ) -> None:
        """Create an ADS-B client.

        Args:
            host: Hostname or IP exposing Beast binary data.
            port: TCP port exposing Beast binary data, normally 30005.
            receiver_location: Local antenna location used for distance sorting.
            timeout_s: Maximum time to spend connecting/reading per update.
            max_age_s: Seconds before an aircraft is dropped from display state.
        """
        self.host = host
        self.port = port
        self.receiver_location = receiver_location
        self.timeout_s = timeout_s
        self.max_age_s = max_age_s
        self._buffer = bytearray()
        self._aircraft: dict[str, AircraftState] = {}

    def update(self, max_planes: int) -> list[Plane]:
        """Read available Beast messages and return nearest tracked aircraft.

        Args:
            max_planes: Maximum number of aircraft to return.

        Returns:
            Aircraft ordered by nearest known distance.
        """
        now = time.time()
        deadline = time.monotonic() + self.timeout_s
        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout_s,
            ) as sock:
                sock.settimeout(max(0.1, self.timeout_s))
                while time.monotonic() < deadline:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    self._buffer.extend(chunk)
                    for frame in parse_beast_frames(self._buffer):
                        self._process_frame(frame, now)
        except OSError as err:
            print(f"Error: Failed to fetch ADS-B Beast data from {self.host}:{self.port}")
            print(err)

        self._expire_old_aircraft(now)
        return self.nearest_planes(max_planes)

    def nearest_planes(self, max_planes: int) -> list[Plane]:
        """Return nearest planes with known positions.

        Args:
            max_planes: Maximum number of aircraft to return.

        Returns:
            Aircraft sorted by distance in nautical miles.
        """
        planes = [
            state.plane
            for state in self._aircraft.values()
            if state.plane.distance_nm is not None
        ]
        return sorted(planes, key=lambda plane: plane.distance_nm or math.inf)[:max_planes]

    def _process_frame(self, frame: BeastFrame, now: float) -> None:
        if len(frame.payload) not in (7, 14):
            return
        decode_adsb_message(frame.payload, self._aircraft, self.receiver_location, now)

    def _expire_old_aircraft(self, now: float) -> None:
        expired = [
            icao
            for icao, state in self._aircraft.items()
            if now - state.plane.last_seen > self.max_age_s
        ]
        for icao in expired:
            del self._aircraft[icao]


def parse_beast_frames(buffer: bytearray) -> list[BeastFrame]:
    """Parse complete Beast binary frames from a mutable byte buffer.

    Args:
        buffer: Mutable buffer containing raw TCP bytes. Consumed bytes are
            deleted, incomplete trailing bytes are retained.

    Returns:
        Complete decoded Beast frames.
    """
    frames: list[BeastFrame] = []
    index = 0
    while index < len(buffer):
        if buffer[index] != BEAST_ESCAPE:
            index += 1
            continue
        if index + 1 >= len(buffer):
            break

        frame_type = chr(buffer[index + 1])
        payload_length = {"1": 2, "2": 7, "3": 14}.get(frame_type)
        if payload_length is None:
            index += 1
            continue

        payload_start = index + 2
        payload = bytearray()
        cursor = payload_start
        while cursor < len(buffer) and len(payload) < payload_length + 8:
            byte = buffer[cursor]
            if byte == BEAST_ESCAPE:
                if cursor + 1 >= len(buffer):
                    break
                if buffer[cursor + 1] != BEAST_ESCAPE:
                    break
                payload.append(BEAST_ESCAPE)
                cursor += 2
            else:
                payload.append(byte)
                cursor += 1

        total_payload_length = payload_length + 8
        if len(payload) < total_payload_length:
            break

        frames.append(BeastFrame(frame_type=frame_type, payload=bytes(payload[8:])))
        index = cursor

    if index > 0:
        del buffer[:index]
    return frames


def decode_adsb_message(
    message: bytes,
    aircraft: dict[str, AircraftState],
    receiver_location: ReceiverLocation,
    now: float,
) -> None:
    """Decode supported ADS-B message fields into aircraft state.

    Args:
        message: 7-byte or 14-byte Mode S message payload.
        aircraft: Mutable aircraft state keyed by ICAO address.
        receiver_location: Receiver location used to calculate distances.
        now: Timestamp to record for the aircraft update.
    """
    if len(message) != 14:
        return

    downlink_format = message[0] >> 3
    if downlink_format not in (17, 18):
        return

    icao = message[1:4].hex().upper()
    state = aircraft.setdefault(icao, AircraftState(plane=Plane(icao=icao)))
    plane = state.plane
    plane.last_seen = now

    me = message[4:11]
    type_code = me[0] >> 3
    match type_code:
        case 1 | 2 | 3 | 4:
            plane.callsign = decode_callsign(me)
        case code if 9 <= code <= 18:
            plane.altitude_ft = decode_altitude(me)
            cpr = decode_cpr_position(me, now)
            if cpr.odd:
                state.odd_cpr = cpr
            else:
                state.even_cpr = cpr
            position = resolve_global_position(state.even_cpr, state.odd_cpr)
            if position is not None:
                plane.latitude, plane.longitude = position
                plane.distance_nm = haversine_nm(
                    receiver_location.latitude,
                    receiver_location.longitude,
                    plane.latitude,
                    plane.longitude,
                )
        case 19:
            speed, track, vertical_rate = decode_velocity(me)
            plane.ground_speed_kt = speed
            plane.track_deg = track
            plane.vertical_rate_fpm = vertical_rate
        case _:
            return


def decode_callsign(me: bytes) -> str:
    """Decode an ADS-B aircraft identification callsign."""
    value = int.from_bytes(me, byteorder="big") & ((1 << 48) - 1)
    chars = []
    for shift in range(42, -1, -6):
        chars.append(_callsign_char((value >> shift) & 0x3F))
    return "".join(chars).strip()


def decode_altitude(me: bytes) -> int | None:
    """Decode barometric altitude from an airborne position message."""
    raw = ((me[1] << 4) | (me[2] >> 4)) & 0xFFF
    q_bit = (raw >> 4) & 1
    if q_bit == 0:
        return None
    n = ((raw & 0xFE0) >> 1) | (raw & 0x00F)
    return (n * 25) - 1000


def encode_altitude_25ft(altitude_ft: int) -> int:
    """Encode a 25 ft-step ADS-B altitude value for tests and fixtures."""
    n = int((altitude_ft + 1000) / 25)
    return ((n & 0x7F0) << 1) | 0x10 | (n & 0x00F)


def decode_cpr_position(me: bytes, now: float) -> CprPosition:
    """Decode raw CPR latitude/longitude from an airborne position message."""
    odd = bool(me[2] & 0x04)
    lat = ((me[2] & 0x03) << 15) | (me[3] << 7) | (me[4] >> 1)
    lon = ((me[4] & 0x01) << 16) | (me[5] << 8) | me[6]
    return CprPosition(latitude=lat, longitude=lon, odd=odd, timestamp=now)


def resolve_global_position(
    even: CprPosition | None,
    odd: CprPosition | None,
) -> tuple[float, float] | None:
    """Resolve paired even/odd airborne CPR messages to latitude/longitude."""
    if even is None or odd is None:
        return None
    if abs(even.timestamp - odd.timestamp) > 10:
        return None

    lat_even = even.latitude / CPR_SCALE
    lat_odd = odd.latitude / CPR_SCALE
    j = math.floor((59 * lat_even) - (60 * lat_odd) + 0.5)

    dlat_even = 360.0 / 60.0
    dlat_odd = 360.0 / 59.0
    rlat_even = dlat_even * ((j % 60) + lat_even)
    rlat_odd = dlat_odd * ((j % 59) + lat_odd)
    if rlat_even >= 270:
        rlat_even -= 360
    if rlat_odd >= 270:
        rlat_odd -= 360
    if _cpr_nl(rlat_even) != _cpr_nl(rlat_odd):
        return None

    latest = odd if odd.timestamp > even.timestamp else even
    if latest.odd:
        ni = max(_cpr_nl(rlat_odd) - 1, 1)
        m = math.floor(
            (even.longitude * (_cpr_nl(rlat_odd) - 1) - odd.longitude * _cpr_nl(rlat_odd))
            / CPR_SCALE
            + 0.5,
        )
        lon = (360.0 / ni) * ((m % ni) + (odd.longitude / CPR_SCALE))
        lat = rlat_odd
    else:
        ni = max(_cpr_nl(rlat_even), 1)
        m = math.floor(
            (even.longitude * (_cpr_nl(rlat_even) - 1) - odd.longitude * _cpr_nl(rlat_even))
            / CPR_SCALE
            + 0.5,
        )
        lon = (360.0 / ni) * ((m % ni) + (even.longitude / CPR_SCALE))
        lat = rlat_even

    if lon > 180:
        lon -= 360
    return lat, lon


def decode_velocity(me: bytes) -> tuple[int | None, int | None, int | None]:
    """Decode ground speed, track, and vertical rate from an airborne velocity message."""
    subtype = me[0] & 0x07
    if subtype not in (1, 2):
        return None, None, None

    value = int.from_bytes(me, byteorder="big")
    ew_sign = (value >> 45) & 1
    ew_velocity = ((value >> 35) & 0x3FF) - 1
    ns_sign = (value >> 34) & 1
    ns_velocity = ((value >> 24) & 0x3FF) - 1
    if ew_velocity < 0 or ns_velocity < 0:
        return None, None, None

    east_west = -ew_velocity if ew_sign else ew_velocity
    north_south = -ns_velocity if ns_sign else ns_velocity
    speed = round(math.hypot(east_west, north_south))
    track = round((math.degrees(math.atan2(east_west, north_south)) + 360) % 360)

    vr_sign = (value >> 21) & 1
    vr_raw = ((value >> 11) & 0x1FF) - 1
    vertical_rate = None if vr_raw < 0 else vr_raw * 64 * (-1 if vr_sign else 1)
    return speed, track, vertical_rate


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two coordinates in nautical miles."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def format_plane_summary(plane: Plane) -> str:
    """Build the compact first-row aircraft text."""
    callsign = plane.callsign or plane.icao
    distance = "--.-nm" if plane.distance_nm is None else f"{plane.distance_nm:.1f}nm"
    altitude = "----ft" if plane.altitude_ft is None else f"{plane.altitude_ft}ft"
    return f"{distance}  {callsign}  {altitude}"


def format_plane_details(plane: Plane) -> str:
    """Build scrolling aircraft detail text."""
    fields = [f"ICAO {plane.icao}"]
    if plane.ground_speed_kt is not None:
        fields.append(f"{plane.ground_speed_kt}kt")
    if plane.track_deg is not None:
        fields.append(f"track {plane.track_deg:03d}")
    if plane.vertical_rate_fpm is not None:
        fields.append(f"vs {plane.vertical_rate_fpm:+d}fpm")
    if plane.latitude is not None and plane.longitude is not None:
        fields.append(f"{plane.latitude:.3f},{plane.longitude:.3f}")
    return "  --  ".join(fields)


def build_plane_rows(planes: Iterable[Plane]) -> list[dict[str, str]]:
    """Convert plane state into display-ready rows."""
    rows: list[dict[str, str]] = []
    for plane in planes:
        rows.append(
            {
                "summary": format_plane_summary(plane),
                "details": format_plane_details(plane),
                "distance": "" if plane.distance_nm is None else f"{plane.distance_nm:.1f}nm",
                "altitude": "" if plane.altitude_ft is None else f"{plane.altitude_ft}ft",
            },
        )
    return rows


def _callsign_char(value: int) -> str:
    if value == 32:
        return " "
    if 1 <= value <= 26:
        return chr(ord("A") + value - 1)
    if 48 <= value <= 57:
        return chr(ord("0") + value - 48)
    return " "


def _cpr_nl(latitude: float) -> int:
    if latitude < 0:
        latitude = -latitude
    if latitude >= 87:
        return 1
    a = 1 - math.cos(math.pi / (2 * 15))
    b = math.cos(math.radians(latitude)) ** 2
    return math.floor((2 * math.pi) / math.acos(1 - (a / b)))
