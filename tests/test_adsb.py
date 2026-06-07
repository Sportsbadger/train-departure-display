from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import (  # noqa: E402
    AdsbDataError,
    AdsbRouteDataError,
    build_detail_text,
    build_loop_aircraft_text,
    build_loop_info_text,
    build_summary_text,
    enrich_aircraft_routes,
    fetch_aircraft_json,
    fetch_route_lookup_json,
    format_altitude,
    parse_aircraft,
    parse_route_lookup,
    select_featured_aircraft_index,
    select_secondary_aircraft,
)


def test_fetch_aircraft_json_sends_configured_user_agent(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"aircraft": []}

    def fake_get(url, headers, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("adsb.requests.get", fake_get)

    result = fetch_aircraft_json(
        "http://example.test/readsb/data/aircraft.json",
        timeout_s=2.0,
        user_agent="Mozilla/5.0 TestDisplay",
    )

    assert result == {"aircraft": []}
    assert calls["url"] == "http://example.test/readsb/data/aircraft.json"
    assert calls["headers"] == {"User-Agent": "Mozilla/5.0 TestDisplay"}
    assert calls["timeout"] == 2.0


def test_fetch_route_lookup_json_posts_callsigns_and_positions(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        status_code = 200
        text = "[]"
        content = b"[]"

        def json(self):
            return []

    def fake_post(url, headers, json, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("adsb.requests.post", fake_post)
    aircraft = parse_aircraft(
        {
            "aircraft": [
                {
                    "hex": "abc123",
                    "flight": " BAW15 ",
                    "lat": 51.5,
                    "lon": -0.1,
                    "seen": 1,
                }
            ]
        },
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )

    result = fetch_route_lookup_json(
        "https://api.example.test/api/0/routeset",
        aircraft,
        timeout_s=4.0,
        user_agent="Mozilla/5.0 TestDisplay",
    )

    assert result == []
    assert calls["url"] == "https://api.example.test/api/0/routeset"
    assert calls["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 TestDisplay",
    }
    assert calls["json"] == {
        "planes": [{"callsign": "BAW15", "lat": 51.5, "lng": -0.1}]
    }
    assert calls["timeout"] == 4.0


def test_fetch_route_lookup_json_returns_empty_for_empty_201(monkeypatch):
    class FakeResponse:
        status_code = 201
        text = ""
        content = b""

        def raise_for_status(self):
            return None

    monkeypatch.setattr("adsb.requests.post", lambda *_, **__: FakeResponse())

    result = fetch_route_lookup_json(
        "https://api.example.test/api/0/routeset",
        parse_aircraft(
            {
                "aircraft": [
                    {
                        "hex": "abc123",
                        "flight": "BAW15",
                        "lat": 51.5,
                        "lon": -0.1,
                        "seen": 1,
                    }
                ]
            },
            home_lat=51.5,
            home_lon=-0.1,
            max_age_s=30,
            max_distance_nm=None,
            min_altitude_ft=None,
            limit=5,
        ),
        timeout_s=4.0,
        user_agent="Mozilla/5.0 TestDisplay",
    )

    assert result == []


def test_fetch_route_lookup_json_raises_route_error_for_non_json(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "main"
        content = b"main"

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr("adsb.requests.post", lambda *_, **__: FakeResponse())

    with pytest.raises(AdsbRouteDataError, match="not JSON"):
        fetch_route_lookup_json(
            "https://api.example.test/api/0/routeset",
            parse_aircraft(
                {
                    "aircraft": [
                        {
                            "hex": "abc123",
                            "flight": "BAW15",
                            "lat": 51.5,
                            "lon": -0.1,
                            "seen": 1,
                        }
                    ]
                },
                home_lat=51.5,
                home_lon=-0.1,
                max_age_s=30,
                max_distance_nm=None,
                min_altitude_ft=None,
                limit=5,
            ),
            timeout_s=4.0,
            user_agent="Mozilla/5.0 TestDisplay",
        )


def test_parse_route_lookup_supports_iata_icao_and_city_routes():
    payload = [
        {
            "callsign": "BAW15",
            "_airport_codes_iata": "LHR-SIN-SYD",
            "airport_codes": "EGLL-WSSS-YSSY",
            "_airports": [
                {"iata": "LHR", "icao": "EGLL", "location": "London"},
                {"iata": "SIN", "icao": "WSSS", "location": "Singapore"},
                {"iata": "SYD", "icao": "YSSY", "location": "Sydney"},
            ],
        }
    ]

    iata_routes = parse_route_lookup(payload, "iata")
    icao_routes = parse_route_lookup(payload, "icao")
    city_routes = parse_route_lookup(payload, "city")

    assert iata_routes["BAW15"].origin == "LHR"
    assert iata_routes["BAW15"].destination == "SYD"
    assert icao_routes["BAW15"].origin == "EGLL"
    assert icao_routes["BAW15"].destination == "YSSY"
    assert city_routes["BAW15"].origin == "London"
    assert city_routes["BAW15"].destination == "Sydney"


def test_parse_route_lookup_accepts_wrapped_routes_and_airport_fallbacks():
    payload = {
        "routes": [
            {
                "callsign": "UAL881",
                "_airports": [
                    {"iata": "ORD", "icao": "KORD", "location": "Chicago"},
                    {"iata": "HND", "icao": "RJTT", "location": "Tokyo"},
                ],
            }
        ]
    }

    iata_routes = parse_route_lookup(payload, "iata")
    icao_routes = parse_route_lookup(payload, "icao")

    assert iata_routes["UAL881"].origin == "ORD"
    assert iata_routes["UAL881"].destination == "HND"
    assert icao_routes["UAL881"].origin == "KORD"
    assert icao_routes["UAL881"].destination == "RJTT"


def test_enrich_aircraft_routes_adds_route_to_matching_callsign_detail():
    aircraft = parse_aircraft(
        {
            "aircraft": [
                {
                    "hex": "abc123",
                    "flight": "BAW15",
                    "lat": 51.5,
                    "lon": -0.1,
                    "seen": 1,
                    "t": "A388",
                    "r": "G-XLEA",
                    "desc": "Airbus A380",
                    "gs": 450,
                    "track": 90,
                    "alt_baro": 38000,
                    "tas": 488,
                    "mach": 0.85,
                    "baro_rate": 128,
                    "squawk": "1234",
                },
                {
                    "hex": "def456",
                    "flight": "UNKNOWN",
                    "lat": 51.6,
                    "lon": -0.2,
                    "seen": 1,
                },
            ]
        },
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )

    enriched = enrich_aircraft_routes(
        aircraft,
        [
            {
                "callsign": " BAW15 ",
                "_airport_codes_iata": "LHR-SYD",
            }
        ],
        "iata",
    )

    assert enriched[0].route == "LHR-SYD"
    assert enriched[1].route == ""
    assert build_summary_text(enriched[0]) == (
        "BAW15  LHR-SYD    G-XLEA  A388  488kt  0nm  38000ft"
    )
    assert build_detail_text(enriched[0]) == (
        "Airbus A380  brg 000deg  E 090  gs 450kt  tas 488kt  "
        "mach 0.85  climb 128fpm  sq 1234  ABC123  seen 1s"
    )


def test_parse_route_lookup_rejects_unsupported_payload_shape():
    with pytest.raises(AdsbRouteDataError, match="route response"):
        parse_route_lookup({"callsign": "BAW15"}, "iata")


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


def test_select_featured_aircraft_index_cycles_one_aircraft_at_a_time():
    aircraft = parse_aircraft(
        {
            "aircraft": [
                {"hex": "aaa111", "lat": 51.5, "lon": -0.1, "seen": 1},
                {"hex": "bbb222", "lat": 51.6, "lon": -0.2, "seen": 1},
                {"hex": "ccc333", "lat": 51.7, "lon": -0.3, "seen": 1},
            ]
        },
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )

    assert select_featured_aircraft_index(aircraft, now=0.0, interval_s=10) == 0
    assert select_featured_aircraft_index(aircraft, now=10.0, interval_s=10) == 1
    assert select_featured_aircraft_index(aircraft, now=20.0, interval_s=10) == 2
    assert select_featured_aircraft_index(aircraft, now=30.0, interval_s=10) == 0


def test_select_secondary_aircraft_returns_next_two_ranked_aircraft():
    aircraft = parse_aircraft(
        {
            "aircraft": [
                {"hex": "aaa111", "lat": 51.5, "lon": -0.1, "seen": 1},
                {"hex": "bbb222", "lat": 51.6, "lon": -0.2, "seen": 1},
                {"hex": "ccc333", "lat": 51.7, "lon": -0.3, "seen": 1},
            ]
        },
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )

    secondary = select_secondary_aircraft(aircraft, featured_index=1)

    assert [(position, item.hex) for position, item in secondary] == [
        (3, "ccc333"),
    ]


def test_loop_aircraft_text_places_type_left_and_distance_right():
    aircraft = parse_aircraft(
        {
            "aircraft": [
                {
                    "hex": "abc123",
                    "flight": "BAW15",
                    "lat": 51.5,
                    "lon": -0.1,
                    "seen": 1,
                    "t": "A388",
                    "gs": 450,
                    "track": 90,
                    "alt_baro": 38000,
                }
            ]
        },
        home_lat=51.5,
        home_lon=-0.1,
        max_age_s=30,
        max_distance_nm=None,
        min_altitude_ft=None,
        limit=5,
    )[0]

    assert build_loop_aircraft_text(aircraft, 2) == "2nd  BAW15  A388"
    assert build_loop_info_text(aircraft) == "450kt 0nm 38000ft"


def test_format_altitude_handles_unknown_and_ground():
    assert format_altitude(None) == "----ft"
    assert format_altitude(0) == "Ground"
    assert format_altitude(32000) == "32000ft"
