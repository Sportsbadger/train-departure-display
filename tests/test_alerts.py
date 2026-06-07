from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from alerts import (  # noqa: E402
    MqttAlertListener,
    build_alert_template_text,
    parse_plane_alert_mqtt_payload,
)


def test_parse_plane_alert_mqtt_payload_accepts_json_hit():
    payload = (
        b'{"hex":"AE1234","tail":"N123AB","call":"@SAM123",'
        b'"name":"USAF","equipment":"Boeing C-32A",'
        b'"timestamp":"2026/06/06 11:30:00"}'
    )

    alert = parse_plane_alert_mqtt_payload(
        payload,
        "plane-alert/alerts/hit",
        received_at=datetime(2026, 6, 6, 11, 31, 0),
    )

    assert alert.source == "plane-alert/alerts/hit"
    assert alert.plane_alert.display_name == "SAM123"
    assert alert.plane_alert.tail == "N123AB"
    assert alert.plane_alert.timestamp == datetime(2026, 6, 6, 11, 30, 0)
    assert build_alert_template_text(
        "{title} {display_name} {tail_or_hex} {equipment}",
        alert,
    ) == "PLANE ALERT SAM123 N123AB Boeing C-32A"


def test_parse_plane_alert_mqtt_payload_keeps_plain_text():
    alert = parse_plane_alert_mqtt_payload(
        b"Plane-Alert hit: AE1234",
        "plane-alert/alerts/text",
        received_at=datetime(2026, 6, 6, 11, 31, 0),
    )

    assert alert.raw_text == "Plane-Alert hit: AE1234"
    assert alert.plane_alert.name == "Plane-Alert hit: AE1234"
    assert build_alert_template_text("{raw}", alert) == "Plane-Alert hit: AE1234"


def test_mqtt_alert_listener_promotes_latest_event_and_expires():
    listener = MqttAlertListener(
        {
            "displayDuration": 5.0,
            "mqttClientId": "test",
            "mqttHost": "127.0.0.1",
            "mqttPort": 1883,
            "mqttKeepalive": 60,
            "mqttTopic": "plane-alert/alerts/#",
            "mqttQos": 0,
        }
    )

    listener._on_message(  # noqa: SLF001
        None,
        None,
        type(
            "Message",
            (),
            {"payload": b'{"hex":"AE0001"}', "topic": "plane-alert/alerts/hit"},
        )(),
    )
    listener._on_message(  # noqa: SLF001
        None,
        None,
        type(
            "Message",
            (),
            {"payload": b'{"hex":"AE0002"}', "topic": "plane-alert/alerts/hit"},
        )(),
    )

    active = listener.current_alert(now=10.0)

    assert active is not None
    assert active.plane_alert.hex == "AE0002"
    assert listener.current_alert(now=14.9) == active
    assert listener.current_alert(now=15.1) is None
