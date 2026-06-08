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
    assert calls["url"].endswith("pa_query.php?timestamp=.*&type=json")
    assert calls["headers"]["User-Agent"] == "Mozilla/5.0 TestDisplay"
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
    assert "Boeing C-32A" in build_plane_alert_detail_text(result[0])
    assert "AE1234" in build_plane_alert_detail_text(result[0])


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
        }
    ]

    result = parse_plane_alerts(payload, max_age_hours=None, limit=5)

    assert len(result) == 1
    assert result[0].hex == "AE1234"
    assert result[0].display_name == "SAM123"
    assert result[0].name == "USAF"
    assert result[0].equipment == "Boeing C-32A"
    assert result[0].timestamp == datetime(2026, 6, 6, 11, 30, 0)


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
