from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import requests

TIMESTAMP_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M",
)


@dataclass(frozen=True)
class PlaneAlert:
    """Display-ready Plane-Alert record from docker-planefence."""

    hex: str
    tail: str
    call: str
    name: str
    equipment: str
    timestamp: datetime | None
    lat: float | None
    lon: float | None

    @property
    def display_name(self) -> str:
        """Return the preferred Plane-Alert label for display."""
        if self.call:
            return self.call.removeprefix("@")
        if self.tail:
            return self.tail
        return self.hex.upper()


class PlaneAlertDataError(ValueError):
    """Raised when Plane-Alert data cannot be parsed or validated."""


def fetch_plane_alert_json(
    source_url: str,
    timeout_s: float,
    user_agent: str,
) -> Any:
    """Fetch JSON from a docker-planefence Plane-Alert query endpoint.

    Args:
        source_url: HTTP URL for ``pa_query.php`` including query parameters.
        timeout_s: Maximum request time in seconds.
        user_agent: HTTP User-Agent header for reverse proxies.

    Returns:
        Decoded JSON payload.

    Raises:
        requests.RequestException: If the HTTP request fails or times out.
    """
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": user_agent,
    }
    response = requests.get(source_url, headers=headers, timeout=timeout_s)
    response.raise_for_status()
    return response.json()


def parse_plane_alerts(
    payload: Any,
    max_age_hours: float | None,
    limit: int,
    now: datetime | None = None,
) -> list[PlaneAlert]:
    """Parse, filter, and sort Plane-Alert records by timestamp descending.

    Args:
        payload: Decoded ``pa_query.php`` JSON payload.
        max_age_hours: Optional maximum alert age in hours.
        limit: Maximum number of alerts to return.
        now: Optional current time used by tests.

    Returns:
        Latest matching Plane-Alert records.

    Raises:
        PlaneAlertDataError: If the payload shape is unsupported.
    """
    records = _extract_records(payload)
    alerts = [
        parsed
        for item in records
        if isinstance(item, Mapping)
        for parsed in [_parse_plane_alert_item(item)]
        if parsed is not None
    ]
    filtered = [
        alert
        for alert in alerts
        if _passes_age_filter(alert, max_age_hours, now)
    ]
    return sorted(
        filtered,
        key=lambda alert: alert.timestamp or datetime.min,
        reverse=True,
    )[:limit]


def select_plane_alert_scroll_alerts(
    alerts: Sequence[PlaneAlert],
    display_count: int,
) -> list[PlaneAlert]:
    """Return Plane-Alert records for the lower scrolling rows.

    Args:
        alerts: Newest-first Plane-Alert records, including the highlighted
            record at position zero.
        display_count: Total number of aircraft to display, including the
            highlighted record.

    Returns:
        Aircraft after the highlighted record, capped by ``display_count``.
    """
    if display_count <= 1:
        return []
    return list(alerts[1:display_count])


def build_plane_alert_detail_text(alert: PlaneAlert) -> str:
    """Build the scrolling detail line for a Plane-Alert record."""
    parts = [alert.equipment, alert.name, alert.hex.upper()]
    if alert.lat is not None and alert.lon is not None:
        parts.append(f"{alert.lat:.3f},{alert.lon:.3f}")
    if alert.timestamp is not None:
        parts.append(alert.timestamp.strftime("%d %b %H:%M"))
    return "  ".join(part for part in parts if part)


def format_plane_alert_timestamp(timestamp: datetime | None) -> str:
    """Format a Plane-Alert timestamp for the compact display."""
    if timestamp is None:
        return "--:--"
    return timestamp.strftime("%H:%M")


def _extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        raise PlaneAlertDataError("Plane-Alert response must be a JSON list or object")

    for key in ("data", "records", "alerts", "plane_alert", "plane-alert"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if all(isinstance(value, Mapping) for value in payload.values()):
        return list(payload.values())

    raise PlaneAlertDataError("Plane-Alert response must contain a records list")


def _parse_plane_alert_item(item: Mapping[str, Any]) -> PlaneAlert | None:
    hex_value = _first_clean_text(item, "hex", "icao", "icao_hex")
    tail = _first_clean_text(item, "tail", "tail_number", "registration")
    call = _first_clean_text(item, "call", "callsign", "flight")
    if not any((hex_value, tail, call)):
        return None

    return PlaneAlert(
        hex=hex_value,
        tail=tail,
        call=call,
        name=_first_clean_text(item, "name", "owner"),
        equipment=_first_clean_text(item, "equipment", "type", "aircraft_type"),
        timestamp=_parse_timestamp(
            _first_clean_text(item, "timestamp", "first_seen", "last_seen"),
        ),
        lat=_optional_float(item.get("lat", item.get("latitude"))),
        lon=_optional_float(item.get("lon", item.get("longitude"))),
    )


def _passes_age_filter(
    alert: PlaneAlert,
    max_age_hours: float | None,
    now: datetime | None,
) -> bool:
    if max_age_hours is None or alert.timestamp is None:
        return True
    comparison_now = (now or datetime.now()).replace(tzinfo=None)
    return comparison_now - alert.timestamp <= timedelta(hours=max_age_hours)


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)
    for date_format in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return None


def _first_clean_text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = _clean_text(item.get(key))
        if text:
            return text
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
