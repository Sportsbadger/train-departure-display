from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import (  # noqa: E402
    BEAST_ESCAPE,
    AircraftState,
    CprPosition,
    Plane,
    ReceiverLocation,
    build_plane_rows,
    decode_adsb_message,
    decode_callsign,
    decode_cpr_position,
    encode_altitude_25ft,
    format_plane_details,
    format_plane_summary,
    haversine_nm,
    parse_beast_frames,
    resolve_global_position,
)


def _callsign_me(callsign: str) -> bytes:
    alphabet = {" ": 32}
    alphabet.update({chr(ord("A") + index): index + 1 for index in range(26)})
    alphabet.update({str(index): 48 + index for index in range(10)})
    value = 0
    for char in callsign.ljust(8)[:8]:
        value = (value << 6) | alphabet[char]
    return bytes([(1 << 3)]) + value.to_bytes(6, byteorder="big")[-6:]


def _airborne_position_me(altitude_ft: int, odd: bool, lat: int, lon: int) -> bytes:
    altitude = encode_altitude_25ft(altitude_ft)
    data = bytearray(7)
    data[0] = 9 << 3
    data[1] = (altitude >> 4) & 0xFF
    data[2] = ((altitude & 0x0F) << 4) | (0x04 if odd else 0) | ((lat >> 15) & 0x03)
    data[3] = (lat >> 7) & 0xFF
    data[4] = ((lat & 0x7F) << 1) | ((lon >> 16) & 0x01)
    data[5] = (lon >> 8) & 0xFF
    data[6] = lon & 0xFF
    return bytes(data)


def test_parse_beast_frames_unescapes_payload_and_retains_partial():
    buffer = bytearray(
        [
            BEAST_ESCAPE,
            ord("3"),
            *([0] * 8),
            0x8D,
            BEAST_ESCAPE,
            BEAST_ESCAPE,
            *([1] * 12),
            BEAST_ESCAPE,
            ord("3"),
            0,
        ],
    )

    frames = parse_beast_frames(buffer)

    assert len(frames) == 1
    assert frames[0].frame_type == "3"
    assert frames[0].payload == bytes([0x8D, BEAST_ESCAPE, *([1] * 12)])
    assert buffer == bytearray([BEAST_ESCAPE, ord("3"), 0])


def test_decode_callsign():
    assert decode_callsign(_callsign_me("BAW123")) == "BAW123"


def test_decode_cpr_position_extracts_raw_fields():
    me = _airborne_position_me(altitude_ft=38000, odd=True, lat=93000, lon=51372)
    cpr = decode_cpr_position(me, now=123.0)

    assert cpr == CprPosition(latitude=93000, longitude=51372, odd=True, timestamp=123.0)


def test_resolve_global_position_known_pair():
    even = CprPosition(latitude=93000, longitude=51372, odd=False, timestamp=10.0)
    odd = CprPosition(latitude=74158, longitude=50194, odd=True, timestamp=11.0)

    lat, lon = resolve_global_position(even, odd)

    assert lat == pytest.approx(52.2658, abs=0.001)
    assert lon == pytest.approx(3.9389, abs=0.001)


def test_decode_adsb_message_updates_callsign_and_position():
    aircraft: dict[str, AircraftState] = {}
    receiver = ReceiverLocation(latitude=52.0, longitude=4.0)
    icao = bytes.fromhex("ABCDEF")
    decode_adsb_message(bytes([0x8D]) + icao + _callsign_me("EZY42") + bytes(3), aircraft, receiver, 1.0)
    decode_adsb_message(
        bytes([0x8D]) + icao + _airborne_position_me(30000, False, 93000, 51372) + bytes(3),
        aircraft,
        receiver,
        2.0,
    )
    decode_adsb_message(
        bytes([0x8D]) + icao + _airborne_position_me(30000, True, 74158, 50194) + bytes(3),
        aircraft,
        receiver,
        3.0,
    )

    plane = aircraft["ABCDEF"].plane
    assert plane.callsign == "EZY42"
    assert plane.altitude_ft == 30000
    assert plane.latitude is not None
    assert plane.longitude is not None
    assert plane.distance_nm is not None


def test_plane_formatting_and_distance():
    plane = Plane(
        icao="ABCDEF",
        callsign="BAW123",
        altitude_ft=12000,
        ground_speed_kt=280,
        track_deg=91,
        vertical_rate_fpm=-640,
        latitude=51.5,
        longitude=-0.1,
        distance_nm=4.25,
    )

    assert haversine_nm(51.5, -0.1, 51.5, -0.1) == 0
    assert format_plane_summary(plane) == "4.2nm  BAW123  12000ft"
    assert format_plane_details(plane) == "ICAO ABCDEF  --  280kt  --  track 091  --  vs -640fpm  --  51.500,-0.100"
    assert build_plane_rows([plane])[0]["distance"] == "4.2nm"
