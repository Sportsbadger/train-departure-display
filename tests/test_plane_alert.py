from datetime import datetime
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from plane_alert import (  # noqa: E402
    LAST_LINE_TEXT,
    PlaneAlertDataError,
    build_plane_alert_detail_text,
    build_plane_alert_template_text,
    fetch_plane_alert_json,
    format_plane_alert_timestamp,
    parse_plane_alerts,
    select_featured_plane_alert_index,
    select_plane_alert_scroll_alerts,
    select_secondary_plane_alert_display_rows,
)


def test_fetch_plane_alert_json_sends_configured_user_agent(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"hex": "AE1234"}]

    def fake_get(url, headers, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("plane_alert.requests.get", fake_get)

    result = fetch_plane_alert_json(
        "http://example.test/plane-alert/pa_query.php?timestamp=.*&type=json",
        timeout_s=2.0,
        user_agent="Mozilla/5.0 TestDisplay",
    )

    assert result == [{"hex": "AE1234"}]
    assert calls["url"] == (
        "http://example.test:8083/cgi/stream.sh?mode=plane-alert&date=all"
    )
    assert calls["headers"]["User-Agent"] == "Mozilla/5.0 TestDisplay"
    assert calls["headers"]["Accept-Language"].startswith("en-GB")
    assert "application/json" in calls["headers"]["Accept"]
    assert "gzip" in calls["headers"]["Accept-Encoding"]
    assert calls["timeout"] == 2.0


def test_fetch_plane_alert_json_reports_non_json_response(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "<html>not json</html>"

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("not json")

    def fake_get(url, headers, timeout):
        return FakeResponse()

    monkeypatch.setattr("plane_alert.requests.get", fake_get)

    with pytest.raises(PlaneAlertDataError, match="not JSON"):
        fetch_plane_alert_json(
            "http://example.test/plane-alert/pa_query.php?timestamp=.*&type=json",
            timeout_s=2.0,
            user_agent="Mozilla/5.0 TestDisplay",
        )


def test_parse_plane_alerts_sorts_filters_and_accepts_wrapped_records():
    payload = {
        "data": [
            {
                "hex": "old111",
                "tail": "NOLD",
                "call": "OLD1",
                "name": "Old Owner",
                "equipment": "Cessna 172",
                "timestamp": "2026/06/04 12:00:00",
            },
            {
                "hex": "AE1234",
                "tail": "N123AB",
                "call": "@SAM123",
                "name": "USAF",
                "equipment": "Boeing C-32A",
                "timestamp": "2026/06/06 11:30:00",
                "lat": "51.500",
                "lon": "-0.100",
            },
            {
                "hex": "AE5678",
                "tail": "N567AB",
                "call": "RCH567",
                "timestamp": "2026/06/06 10:30:00",
            },
        ]
    }

    result = parse_plane_alerts(
        payload,
        max_age_hours=24,
        limit=5,
        now=datetime(2026, 6, 6, 12, 0, 0),
    )

    assert [alert.display_name for alert in result] == ["SAM123", "RCH567"]
    assert result[0].lat == 51.5
    detail_text = build_plane_alert_detail_text(result[0])

    assert "Boeing C-32A" in detail_text
    assert "AE1234" not in detail_text
    assert "06 Jun" not in detail_text


def test_parse_plane_alerts_applies_configured_time_offset():
    result = parse_plane_alerts(
        [
            {
                "icao": "AE0001",
                "callsign": "BST1",
                "time:lastseen": "2026/06/06 11:30:00",
            }
        ],
        max_age_hours=None,
        limit=1,
        time_offset_hours=1.0,
    )

    assert result[0].timestamp == datetime(2026, 6, 6, 12, 30, 0)
    assert format_plane_alert_timestamp(result[0].timestamp) == "12:30"

def test_parse_plane_alerts_accepts_docker_planefence_query_keys():
    payload = [
        {
            "index": "101",
            "icao": "AE1234",
            "tail": "N123AB",
            "callsign": "@SAM123",
            "owner": "USAF",
            "type": "Boeing C-32A",
            "time:time_at_mindist": "2026/06/06 11:30:00",
            "lat": "51.500",
            "lon": "-0.100",
            "db category": "Military",
            "db tag1": "VIP",
            "db tag2": "Widebody",
            "db tag3": "Priority",
            "route": "ADW-LHR",
        }
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=5)

    assert len(result) == 1
    assert result[0].hex == "AE1234"
    assert result[0].display_name == "SAM123"
    assert result[0].name == "USAF"
    assert result[0].equipment == "Boeing C-32A"
    assert result[0].timestamp == datetime(2026, 6, 6, 11, 30, 0)
    assert result[0].db_category == "Military"
    assert result[0].db_tag1 == "VIP"
    assert result[0].db_tag2 == "Widebody"
    assert result[0].db_tag3 == "Priority"
    assert result[0].route == "ADW-LHR"


def test_decode_plane_alert_response_accepts_ndjson_and_index_sorting():
    from plane_alert import decode_plane_alert_response

    payload = "\n".join(
        [
            '{"index":"329","icao":"A7C683","callsign":"N60SN",'
            '"tail":"N60SN","type":"FA8X","owner":"SONY AVIATION",'
            '"distance:value":"66.63","altitude:value":"41000"}',
            '{"index":null,"icao":"SKIPME"}',
            '{"index":"bad","icao":"SKIPME2"}',
            '{"index":"330","icao":"440890","callsign":"TYW758",'
            '"tail":"OE-GKW","type":"ASTR","owner":"TYROL AIR AMBULANCE",'
            '"time:lastseen":"2026/06/06 11:31:00",'
            '"distance:value":"26.12","distance:unit":"nm",'
            '"altitude:value":"17000","altitude:unit":"ft"}',
        ]
    )

    result = parse_plane_alerts(
        decode_plane_alert_response(payload),
        max_age_hours=None,
        limit=10,
    )

    assert [alert.hex for alert in result] == ["440890", "A7C683"]
    assert result[0].index == 330
    assert result[0].display_index == 331
    assert result[0].distance == "26.12 nm"
    assert result[0].altitude == "17000 ft"


def test_parse_plane_alerts_returns_30_most_recent_indexed_records():
    payload = [
        {
            "index": str(index),
            "icao": f"AE{index:04d}",
            "callsign": f"TEST{index}",
        }
        for index in range(40)
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=30)

    assert len(result) == 30
    assert [alert.index for alert in result] == list(range(39, 9, -1))
    assert [alert.display_index for alert in result[:3]] == [40, 39, 38]


def test_parse_plane_alerts_uses_timestamp_when_no_numeric_index_exists():
    payload = [
        {
            "index": None,
            "icao": "AE0001",
            "callsign": "OLD",
            "time:lastseen": "2026/06/06 10:00:00",
        },
        {
            "index": "bad",
            "icao": "AE0002",
            "callsign": "NEW",
            "time:lastseen": "2026/06/06 11:00:00",
        },
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=5)

    assert [alert.hex for alert in result] == ["AE0002", "AE0001"]


def test_parse_plane_alerts_accepts_millisecond_unix_timestamps():
    payload = [
        {
            "index": "1",
            "icao": "AE0001",
            "callsign": "TEST1",
            "time:lastseen": "1780704000000",
        }
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=5)

    assert result[0].timestamp == datetime(2026, 6, 6, 0, 0, 0)


def test_parse_plane_alerts_accepts_mapping_of_records_and_limit():
    payload = {
        "AE0001": {"hex": "AE0001", "timestamp": "2026/06/06 10:00:00"},
        "AE0002": {"hex": "AE0002", "timestamp": "2026/06/06 11:00:00"},
    }

    result = parse_plane_alerts(payload, max_age_hours=None, limit=1)

    assert len(result) == 1
    assert result[0].hex == "AE0002"


def test_parse_plane_alerts_rejects_unsupported_payload_shape():
    with pytest.raises(PlaneAlertDataError, match="records list"):
        parse_plane_alerts({"count": 1}, max_age_hours=None, limit=5)


def test_format_plane_alert_timestamp_handles_unknown():
    assert format_plane_alert_timestamp(None) == "--:--"
    assert format_plane_alert_timestamp(datetime(2026, 6, 6, 9, 5)) == "09:05"


def test_select_plane_alert_scroll_alerts_skips_highlighted_record():
    alerts = parse_plane_alerts(
        [
            {"hex": "AE0001", "timestamp": "2026/06/06 10:00:00"},
            {"hex": "AE0002", "timestamp": "2026/06/06 09:00:00"},
            {"hex": "AE0003", "timestamp": "2026/06/06 08:00:00"},
        ],
        max_age_hours=None,
        limit=3,
    )

    result = select_plane_alert_scroll_alerts(alerts, display_count=2)

    assert [alert.hex for alert in result] == ["AE0002"]
    assert select_plane_alert_scroll_alerts(alerts, display_count=1) == []


def test_build_plane_alert_template_text_handles_defaults_and_unknowns():
    alert = parse_plane_alerts(
        [
            {
                "hex": "AE1234",
                "tail": "N123AB",
                "call": "@SAM123",
                "name": "USAF",
                "equipment": "Boeing C-32A",
                "timestamp": "2026/06/06 11:30:00",
            }
        ],
        max_age_hours=None,
        limit=1,
    )[0]

    assert (
        build_plane_alert_template_text("{summary_left}", alert)
        == "SAM123  N123AB  11:30"
    )
    assert build_plane_alert_template_text("{summary_right}", alert) == "AE1234"
    assert (
        build_plane_alert_template_text("{loop_alert}", alert, 2)
        == "2nd  SAM123  N123AB"
    )
    assert build_plane_alert_template_text("{missing}", alert) == ""


def test_build_plane_alert_template_text_includes_db_tags_and_route():
    alert = parse_plane_alerts(
        [
            {
                "hex": "AE1234",
                "db category": "Military",
                "db tag1": "VIP",
                "db tag2": "Widebody",
                "db tag3": "Priority",
                "route": "ADW-LHR",
            }
        ],
        max_age_hours=None,
        limit=1,
    )[0]

    assert (
        build_plane_alert_template_text(
            "{db_category} {db_tag1} {db_tag2} {db_tag3} {route}",
            alert,
        )
        == "Military VIP Widebody Priority ADW-LHR"
    )
    assert (
        build_plane_alert_template_text(
            "{db category} {db tag1} {db tag2} {db tag3}",
            alert,
        )
        == "Military VIP Widebody Priority"
    )
    assert "ADW-LHR" in build_plane_alert_detail_text(alert)


def test_select_featured_plane_alert_index_cycles_one_alert_at_a_time():
    alerts = parse_plane_alerts(
        [
            {"hex": "AE0001", "timestamp": "2026/06/06 10:00:00"},
            {"hex": "AE0002", "timestamp": "2026/06/06 09:00:00"},
            {"hex": "AE0003", "timestamp": "2026/06/06 08:00:00"},
        ],
        max_age_hours=None,
        limit=3,
    )

    assert select_featured_plane_alert_index(alerts, now=0.0, interval_s=10) == 0
    assert select_featured_plane_alert_index(alerts, now=10.0, interval_s=10) == 1
    assert select_featured_plane_alert_index(alerts, now=20.0, interval_s=10) == 2
    assert select_featured_plane_alert_index(alerts, now=30.0, interval_s=10) == 0


def test_select_secondary_plane_alert_display_rows_adds_last_line_marker():
    alerts = parse_plane_alerts(
        [
            {"hex": "AE0001", "timestamp": "2026/06/06 10:00:00"},
            {"hex": "AE0002", "timestamp": "2026/06/06 09:00:00"},
            {"hex": "AE0003", "timestamp": "2026/06/06 08:00:00"},
        ],
        max_age_hours=None,
        limit=3,
    )

    rows = select_secondary_plane_alert_display_rows(alerts, featured_index=1)

    assert [
        (position, item.hex if item is not None else LAST_LINE_TEXT)
        for position, item in rows
    ] == [
        (3, "AE0003"),
        (None, LAST_LINE_TEXT),
    ]
    assert select_secondary_plane_alert_display_rows(alerts, featured_index=2) == [
        (None, None),
    ]


def test_ensure_plane_alert_api_url_upgrades_legacy_query_endpoint():
    from plane_alert import ensure_plane_alert_api_url

    assert ensure_plane_alert_api_url(
        "http://host/plane-alert/pa_query.php?timestamp=.*"
    ) == "http://host:8083/cgi/stream.sh?mode=plane-alert&date=all"
    assert ensure_plane_alert_api_url(
        "http://host:9999/plane-alert/pa_query.php?timestamp=.*"
    ) == "http://host:9999/cgi/stream.sh?mode=plane-alert&date=all"
    assert ensure_plane_alert_api_url(
        "http://host/cgi/stream.sh?ts=123"
    ) == "http://host:8083/cgi/stream.sh?ts=123&mode=plane-alert&date=all"


def test_decode_plane_alert_response_accepts_utf8_sig_csv():
    from plane_alert import decode_plane_alert_response

    payload = (
        "\ufeffhex,tail,name,equipment,timestamp,call,lat,lon\n"
        'AE1234,N123AB,"USAF, Special",Boeing C-32A,'
        "2026/06/06 11:30:00,@SAM123,51.5,-0.1\n"
    )

    result = parse_plane_alerts(
        decode_plane_alert_response(payload),
        max_age_hours=None,
        limit=5,
    )

    assert len(result) == 1
    assert result[0].hex == "AE1234"
    assert result[0].name == "USAF, Special"
    assert result[0].display_name == "SAM123"
    assert result[0].lat == 51.5


def test_parse_plane_alerts_deduplicates_with_more_complete_record():
    payload = [
        {"hex": "AE1234", "timestamp": "2026/06/06 11:30:00"},
        {
            "hex": "AE1234",
            "tail": "N123AB",
            "equipment": "Boeing C-32A",
            "timestamp": "2026/06/06 11:30:00",
        },
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=5)

    assert len(result) == 1
    assert result[0].tail == "N123AB"
    assert result[0].equipment == "Boeing C-32A"
