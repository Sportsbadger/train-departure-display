from __future__ import annotations

import importlib
import importlib.util
import json
import queue
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from plane_alert import PlaneAlert, build_plane_alert_template_text

_paho_spec = importlib.util.find_spec("paho")
_mqtt_spec = importlib.util.find_spec("paho.mqtt.client") if _paho_spec else None
mqtt = importlib.import_module("paho.mqtt.client") if _mqtt_spec else None


@dataclass(frozen=True)
class DisplayAlert:
    """A display-ready high-priority alert event."""

    source: str
    received_at: datetime
    plane_alert: PlaneAlert
    raw_text: str = ""

    @property
    def key(self) -> str:
        """Return a stable key for display change detection."""
        timestamp = int(self.received_at.timestamp())
        return (
            f"{self.source}:{self.plane_alert.hex}:"
            f"{self.plane_alert.call}:{timestamp}"
        )


def parse_plane_alert_mqtt_payload(
    payload: bytes,
    topic: str,
    received_at: datetime | None = None,
) -> DisplayAlert:
    """Parse a Plane-Alert MQTT payload into a display alert.

    Args:
        payload: Raw MQTT message payload bytes.
        topic: MQTT topic that delivered the message.
        received_at: Optional receipt time for deterministic tests.

    Returns:
        Display-ready alert. JSON payloads are mapped to Plane-Alert fields;
        non-JSON payloads are retained as raw text and shown as the alert name.
    """
    received = received_at or datetime.now(timezone.utc).replace(tzinfo=None)
    text = payload.decode("utf-8", errors="replace").strip()
    decoded = _decode_json_object(text)
    if decoded is None:
        plane_alert = PlaneAlert(
            hex="",
            tail="",
            call="",
            name=text or topic,
            equipment="",
            timestamp=received.replace(tzinfo=None),
            lat=None,
            lon=None,
        )
        return DisplayAlert(
            source=topic,
            received_at=received.replace(tzinfo=None),
            plane_alert=plane_alert,
            raw_text=text,
        )

    plane_alert = _plane_alert_from_mapping(decoded, received)
    return DisplayAlert(
        source=topic,
        received_at=received.replace(tzinfo=None),
        plane_alert=plane_alert,
        raw_text=text,
    )


def build_alert_template_text(template: str, alert: DisplayAlert) -> str:
    """Build full-screen alert text from a configured template."""
    try:
        return template.format_map(_AlertTemplateContext(alert)).strip()
    except (KeyError, TypeError, ValueError):
        return ""


class MqttAlertListener:
    """Non-blocking MQTT listener for Plane-Alert hit notifications."""

    def __init__(self, mqtt_config: Mapping[str, Any]) -> None:
        """Create a listener using alert MQTT configuration.

        Args:
            mqtt_config: The ``config["alerts"]`` mapping.
        """
        self._config = mqtt_config
        self._events: queue.Queue[DisplayAlert] = queue.Queue(maxsize=10)
        self._client: Any | None = None
        self._active_alert: DisplayAlert | None = None
        self._active_until = 0.0

    def start(self) -> None:
        """Connect and start the MQTT network loop in a background thread."""
        if mqtt is None:
            raise RuntimeError(
                "paho-mqtt is required when alertsEnabled=True; "
                "install requirements.txt before enabling alerts"
            )

        client = mqtt.Client(
            client_id=str(self._config["mqttClientId"]),
            clean_session=True,
        )
        username = str(self._config.get("mqttUsername") or "")
        password = str(self._config.get("mqttPassword") or "")
        if username:
            client.username_pw_set(username, password or None)
        if bool(self._config.get("mqttTlsEnabled", False)):
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect_async(
            str(self._config["mqttHost"]),
            int(self._config["mqttPort"]),
            keepalive=int(self._config["mqttKeepalive"]),
        )
        client.loop_start()
        self._client = client

    def stop(self) -> None:
        """Stop the MQTT background loop without blocking display shutdown."""
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None

    def current_alert(self, now: float | None = None) -> DisplayAlert | None:
        """Return the active alert, promoting queued hits as needed.

        Args:
            now: Optional monotonic timestamp for tests.

        Returns:
            Active display alert or ``None`` when no alert should interrupt.
        """
        current_time = now if now is not None else time.monotonic()
        self._promote_latest_event(current_time)
        if self._active_alert is None:
            return None
        if current_time < self._active_until:
            return self._active_alert
        self._active_alert = None
        return None

    def _on_connect(
        self,
        client: Any,
        _userdata: Any,
        _flags: dict[str, Any],
        return_code: int,
    ) -> None:
        if return_code != 0:
            print(f"Warning: MQTT alert connection failed with code {return_code}")
            return
        client.subscribe(
            str(self._config["mqttTopic"]),
            qos=int(self._config["mqttQos"]),
        )

    def _on_message(
        self,
        _client: Any,
        _userdata: Any,
        message: Any,
    ) -> None:
        try:
            alert = parse_plane_alert_mqtt_payload(message.payload, message.topic)
        except UnicodeDecodeError as err:
            print(f"Warning: Failed to decode MQTT alert payload: {err}")
            return
        _put_drop_oldest(self._events, alert)

    def _promote_latest_event(self, now: float) -> None:
        latest: DisplayAlert | None = None
        while True:
            try:
                latest = self._events.get_nowait()
            except queue.Empty:
                break
        if latest is None:
            return
        self._active_alert = latest
        self._active_until = now + float(self._config["displayDuration"])


class _AlertTemplateContext(dict[str, Any]):
    """Lazy full-screen alert template context."""

    def __init__(self, alert: DisplayAlert) -> None:
        super().__init__()
        self._alert = alert

    def __missing__(self, key: str) -> Any:
        value = _alert_template_value(key, self._alert)
        self[key] = value
        return value


def _alert_template_value(key: str, alert: DisplayAlert) -> Any:
    plane_alert = alert.plane_alert
    match key:
        case "source":
            return alert.source
        case "raw":
            return alert.raw_text
        case "received_time":
            return alert.received_at.strftime("%H:%M")
        case "title":
            return "PLANE ALERT"
        case "headline":
            return build_plane_alert_template_text(
                "{display_name}  {tail_or_hex}  {time}",
                plane_alert,
            )
        case "summary":
            return build_plane_alert_template_text("{summary_left}", plane_alert)
        case "detail":
            return build_plane_alert_template_text("{detail}", plane_alert)
        case _:
            return build_plane_alert_template_text("{" + key + "}", plane_alert)


def _decode_json_object(text: str) -> Mapping[str, Any] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, Mapping):
        return payload
    return None


def _plane_alert_from_mapping(
    payload: Mapping[str, Any],
    received_at: datetime,
) -> PlaneAlert:
    timestamp = _first_clean_text(
        payload,
        "timestamp",
        "first_seen",
        "last_seen",
        "date",
        "time",
    )
    return PlaneAlert(
        hex=_first_clean_text(payload, "hex", "icao", "icao_hex", "icao24"),
        tail=_first_clean_text(payload, "tail", "tail_number", "registration", "reg"),
        call=_first_clean_text(payload, "call", "callsign", "flight"),
        name=_first_clean_text(payload, "name", "owner", "alert", "message"),
        equipment=_first_clean_text(payload, "equipment", "type", "aircraft_type"),
        timestamp=_parse_mqtt_timestamp(timestamp, received_at),
        lat=_optional_float(payload.get("lat", payload.get("latitude"))),
        lon=_optional_float(payload.get("lon", payload.get("longitude"))),
    )


def _parse_mqtt_timestamp(value: str, fallback: datetime) -> datetime:
    if not value:
        return fallback.replace(tzinfo=None)
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)
    for date_format in (
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return fallback.replace(tzinfo=None)


def _first_clean_text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _put_drop_oldest(
    event_queue: queue.Queue[DisplayAlert],
    alert: DisplayAlert,
) -> None:
    try:
        event_queue.put_nowait(alert)
        return
    except queue.Full:
        pass

    try:
        event_queue.get_nowait()
    except queue.Empty:
        pass
    event_queue.put_nowait(alert)
