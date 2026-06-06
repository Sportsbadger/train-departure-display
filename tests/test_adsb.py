from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import (  # noqa: E402
    AdsbDataError,
    build_detail_text,
    format_altitude,
    parse_aircraft,
)


def test_parse_aircraft_sorts_nearest_and_filters_stale_missing_position():
    payload = {
        "aircraft": [
            {
                "hex": "bbb222",
                "flight": " FAR123 ",
                "lat": 51.9,
                "lon": -0.6,
                "seen": 3,
                "alt_baro": 32000,
            },
            {
                "hex": "aaa111",
                "flight": "NEAR1",
                "lat": 51.51,
                "lon": -0.11,
                "seen": 1,
                "alt_baro": "ground",
                "gs": 10,
                "track": 90,
                "baro_rate": 0,
                "squawk": "7000",
                "t": "A20N",
                "r": "G-TEST",
            },
            {
                "hex": "old333",
                "flight": "OLD",
                "lat": 51.52,
                "lon": -0.12,
                "seen": 99,
            },
            {"hex": "nopos", "flight": "NOPOS", "seen": 1},
        ]
    }

    result = parse_aircraft(
        payload,
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )

    assert [aircraft.display_name for aircraft in result] == ["NEAR1", "FAR123"]
    assert result[0].altitude_ft == 0
    assert result[0].aircraft_type == "A20N"
    assert "sq 7000" in build_detail_text(result[0])


def test_parse_aircraft_applies_distance_altitude_and_limit_filters():
    payload = {
        "aircraft": [
            {
                "hex": "low",
                "lat": 51.5001,
                "lon": -0.1001,
                "seen": 1,
                "alt_baro": 1000,
            },
            {
                "hex": "keep1",
                "lat": 51.51,
                "lon": -0.11,
                "seen": 1,
                "alt_baro": 5000,
            },
            {
                "hex": "keep2",
                "lat": 51.52,
                "lon": -0.12,
                "seen": 1,
                "alt_baro": 7000,
            },
        ]
    }

    result = parse_aircraft(
        payload,
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=10,
        min_altitude_ft=4000,
        limit=1,
    )

    assert len(result) == 1
    assert result[0].hex == "keep1"


def test_parse_aircraft_rejects_payload_without_aircraft_list():
    with pytest.raises(AdsbDataError, match="aircraft list"):
        parse_aircraft(
            {},
            home_lat=51.5,
            home_lon=-0.1,
            max_age_s=30,
            max_distance_nm=None,
            min_altitude_ft=None,
            limit=5,
        )


def test_format_altitude_handles_unknown_and_ground():
    assert format_altitude(None) == "----ft"
    assert format_altitude(0) == "Ground"
    assert format_altitude(32000) == "32000ft"
