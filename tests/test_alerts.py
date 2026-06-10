from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from alerts import (  # noqa: E402
    PlaneAlertListAlertListener,
    build_alert_template_text,
    plane_alert_identity,
)
from plane_alert import PlaneAlert  # noqa: E402


def make_alert(
    hex_value: str,
    index: int | None,
    timestamp: datetime | None = None,
) -> PlaneAlert:
    return PlaneAlert(
        hex=hex_value,
        tail=f"N{hex_value[-3:]}",
        call=f"TEST{hex_value[-2:]}",
        name="Owner",
        equipment="Type",
        timestamp=timestamp or datetime(2026, 6, 6, 11, 30, 0),
        lat=None,
        lon=None,
        index=index,
    )


def test_plane_alert_identity_prefers_live_stream_index() -> None:
    alert = make_alert("AE1234", 329)

    assert plane_alert_identity(alert) == "index:329"


def test_plane_alert_list_listener_primes_without_alerting() -> None:
    snapshots = [[make_alert("AE0001", 1)]]
    listener = PlaneAlertListAlertListener(
        {"displayDuration": 5.0, "pollInterval": 1.0},
        {"sourceUrl": "http://example.test/cgi/stream.sh"},
        load_alerts=lambda: snapshots[-1],
    )

    listener.poll_once()

    assert listener.current_alert(now=10.0) is None


def test_plane_alert_list_listener_alerts_when_new_row_is_added() -> None:
    snapshots = [
        [make_alert("AE0001", 1)],
        [make_alert("AE0002", 2), make_alert("AE0001", 1)],
    ]
    calls = 0

    def load_alerts() -> list[PlaneAlert]:
        nonlocal calls
        value = snapshots[calls]
        calls += 1
        return value

    listener = PlaneAlertListAlertListener(
        {"displayDuration": 5.0, "pollInterval": 1.0},
        {"sourceUrl": "http://example.test/cgi/stream.sh"},
        load_alerts=load_alerts,
    )

    listener.poll_once()
    listener.poll_once()
    active = listener.current_alert(now=10.0)

    assert active is not None
    assert active.plane_alert.hex == "AE0002"
    assert build_alert_template_text(
        "{title} {display_name} {tail_or_hex} {equipment}",
        active,
    ) == "PLANE ALERT TEST02 N002 Type"
    assert listener.current_alert(now=14.9) == active
    assert listener.current_alert(now=15.1) is None


def test_plane_alert_list_listener_promotes_latest_added_row() -> None:
    snapshots = [
        [make_alert("AE0001", 1)],
        [make_alert("AE0002", 2), make_alert("AE0001", 1)],
        [
            make_alert("AE0003", 3),
            make_alert("AE0002", 2),
            make_alert("AE0001", 1),
        ],
    ]
    calls = 0

    def load_alerts() -> list[PlaneAlert]:
        nonlocal calls
        value = snapshots[calls]
        calls += 1
        return value

    listener = PlaneAlertListAlertListener(
        {"displayDuration": 5.0, "pollInterval": 1.0},
        {"sourceUrl": "http://example.test/cgi/stream.sh"},
        load_alerts=load_alerts,
    )

    listener.poll_once()
    listener.poll_once()
    listener.poll_once()
    active = listener.current_alert(now=10.0)

    assert active is not None
    assert active.plane_alert.hex == "AE0003"
