from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

import pytest

from adsb import (  # noqa: E402
    ReceiverPosition,
    compass_label,
    format_aircraft_primary,
    format_aircraft_secondary,
    parse_aircraft_payload,
    prepare_display_aircraft,
)
from adsb_source import ADSBDataSource, build_adsb_json_url  # noqa: E402


def test_parse_aircraft_payload_normalizes_fields() -> None:
    aircraft = parse_aircraft_payload(
        {
            "aircraft": [
                {
                    "hex": "40621d",
                    "flight": " BAW123 ",
                    "lat": 51.5,
                    "lon": -0.12,
                    "alt_baro": "12000",
                    "gs": 340.4,
                    "track": 89.9,
                    "baro_rate": -512,
                    "squawk": "1234",
                    "seen": 2.5,
                }
            ]
        }
    )

    assert len(aircraft) == 1
    assert aircraft[0].hex_ident == "40621D"
    assert aircraft[0].callsign == "BAW123"
    assert aircraft[0].altitude_ft == 12000
    assert aircraft[0].ground_speed_kt == 340
    assert aircraft[0].track_deg == 90
    assert aircraft[0].vertical_rate_fpm == -512


def test_parse_aircraft_payload_requires_aircraft_list() -> None:
    with pytest.raises(ValueError, match="aircraft list"):
        parse_aircraft_payload({"now": 123})


def test_prepare_display_aircraft_filters_and_sorts_nearest() -> None:
    aircraft = parse_aircraft_payload(
        {
            "aircraft": [
                {"hex": "far", "lat": 52.0, "lon": -0.12, "seen": 3},
                {"hex": "stale", "lat": 51.51, "lon": -0.12, "seen": 90},
                {"hex": "nopos", "seen": 1},
                {
                    "hex": "near",
                    "flight": "N123AB",
                    "lat": 51.501,
                    "lon": -0.12,
                    "seen": 1,
                },
            ]
        }
    )

    display = prepare_display_aircraft(
        aircraft,
        ReceiverPosition(latitude=51.5, longitude=-0.12),
        max_age_s=30,
        max_aircraft=5,
    )

    assert [item.aircraft.hex_ident for item in display] == ["NEAR", "FAR"]
    assert display[0].bearing_label == "N"


def test_prepare_display_aircraft_applies_optional_filters() -> None:
    aircraft = parse_aircraft_payload(
        {
            "aircraft": [
                {
                    "hex": "low",
                    "lat": 51.501,
                    "lon": -0.12,
                    "alt_baro": 500,
                    "seen": 1,
                },
                {
                    "hex": "ok",
                    "lat": 51.502,
                    "lon": -0.12,
                    "alt_baro": 3000,
                    "seen": 1,
                },
            ]
        }
    )

    display = prepare_display_aircraft(
        aircraft,
        ReceiverPosition(latitude=51.5, longitude=-0.12),
        max_age_s=30,
        max_aircraft=5,
        max_distance_nm=1.0,
        min_altitude_ft=1000,
    )

    assert [item.aircraft.hex_ident for item in display] == ["OK"]


def test_format_aircraft_rows_are_compact() -> None:
    aircraft = parse_aircraft_payload(
        {
            "aircraft": [
                {
                    "hex": "40621d",
                    "flight": "BAW123",
                    "lat": 51.51,
                    "lon": -0.12,
                    "alt_baro": 12500,
                    "gs": 340,
                    "track": 270,
                    "baro_rate": 1024,
                    "squawk": "7000",
                    "seen": 1,
                }
            ]
        }
    )
    display = prepare_display_aircraft(
        aircraft,
        ReceiverPosition(latitude=51.5, longitude=-0.12),
        max_age_s=30,
        max_aircraft=1,
    )

    assert format_aircraft_primary(display[0]) == "BAW123  1nm  N  12k ft"
    assert format_aircraft_secondary(display[0]) == "340kt  Hdg 270  ↑1024  Sq 7000"


def test_compass_label_wraps_north() -> None:
    assert compass_label(359) == "N"
    assert compass_label(45) == "NE"
    assert compass_label(181) == "S"


def test_build_adsb_json_url_prefers_explicit_url() -> None:
    config = {"adsb": {"jsonUrl": "http://feed/aircraft.json"}}

    assert build_adsb_json_url(config) == "http://feed/aircraft.json"


def test_build_adsb_json_url_from_host() -> None:
    config = {
        "adsb": {
            "jsonUrl": "",
            "host": "192.0.2.10",
            "jsonPort": 8080,
            "jsonPath": "data/aircraft.json",
        }
    }

    assert build_adsb_json_url(config) == "http://192.0.2.10:8080/data/aircraft.json"


def test_build_adsb_json_url_requires_source() -> None:
    with pytest.raises(ValueError, match="adsbJsonUrl or adsbHost"):
        build_adsb_json_url({"adsb": {"jsonUrl": "", "host": ""}})


def test_adsb_source_poll_keeps_cached_data_on_failure(monkeypatch) -> None:
    source = ADSBDataSource(
        url="http://example.invalid/aircraft.json",
        refresh_s=5,
        connect_timeout_s=0.1,
        read_timeout_s=0.1,
    )

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[dict[str, object]]]:
            return {"aircraft": [{"hex": "abc123", "seen": 1}]}

    def ok_get(*_args: object, **_kwargs: object) -> Response:
        return Response()

    def bad_get(*_args: object, **_kwargs: object) -> object:
        raise ValueError("bad json")

    monkeypatch.setattr("adsb_source.requests.get", ok_get)
    source.poll()
    assert len(source.aircraft) == 1

    monkeypatch.setattr("adsb_source.requests.get", bad_get)
    source.poll()
    assert len(source.aircraft) == 1
    assert source.last_error == "bad json"


def test_adsb_source_poll_if_due_waits_for_refresh(monkeypatch) -> None:
    source = ADSBDataSource(
        url="http://example.invalid/aircraft.json",
        refresh_s=5,
        connect_timeout_s=0.1,
        read_timeout_s=0.1,
    )
    polls: list[str] = []

    def fake_poll() -> None:
        polls.append("poll")

    monkeypatch.setattr(source, "poll", fake_poll)

    source.poll_if_due(now_monotonic=1.0)
    source.poll_if_due(now_monotonic=3.0)
    source.poll_if_due(now_monotonic=6.0)

    assert polls == ["poll", "poll"]
