from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import requests

LAST_LINE_TEXT = "****Last Line****"

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
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": user_agent,
    }
    response = requests.get(source_url, headers=headers, timeout=timeout_s)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as err:
        body_preview = response.text[:120].strip() or "<empty response>"
        raise PlaneAlertDataError(
            "Plane-Alert response was not JSON "
            f"(HTTP {response.status_code}): {body_preview}"
        ) from err


def parse_plane_alerts(
    payload: Any,
    max_age_minutes: float | None,
    limit: int,
    now: datetime | None = None,
) -> list[PlaneAlert]:
    """Parse, filter, and sort Plane-Alert records by timestamp descending.

    Args:
        payload: Decoded ``pa_query.php`` JSON payload.
        max_age_minutes: Optional maximum alert age in minutes.
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
        if _passes_age_filter(alert, max_age_minutes, now)
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




def select_featured_plane_alert_index(
    alerts: Sequence[PlaneAlert],
    now: float,
    interval_s: float,
) -> int:
    """Select which Plane-Alert record receives the full-detail display.

    Args:
        alerts: Displayable Plane-Alert records ordered newest first.
        now: Monotonic time in seconds.
        interval_s: Seconds to keep each record highlighted.

    Returns:
        Zero-based alert index, or 0 for an empty sequence.
    """
    if not alerts:
        return 0

    safe_interval = max(interval_s, 1.0)
    return int(now // safe_interval) % len(alerts)


def select_secondary_plane_alert_display_rows(
    alerts: Sequence[PlaneAlert],
    featured_index: int,
    window: int = 2,
) -> list[tuple[int | None, PlaneAlert | None]]:
    """Return secondary Plane-Alert rows, ending with a last-line marker.

    Args:
        alerts: Displayable Plane-Alert records ordered newest first.
        featured_index: Zero-based index currently shown with full details.
        window: Maximum number of lower rows to return.

    Returns:
        One-based original positions and alert records for summary rows. A
        ``(None, None)`` row marks the end of the list when it falls within the
        lower-row window.
    """
    if window <= 0:
        return []
    if featured_index >= len(alerts):
        return []

    start = featured_index + 1
    end = start + window
    rows: list[tuple[int | None, PlaneAlert | None]] = [
        (idx + 1, alert)
        for idx, alert in enumerate(alerts[start:end], start=start)
    ]
    if len(rows) < window:
        rows.append((None, None))
    return rows


class _PlaneAlertTemplateContext(dict[str, Any]):
    """Lazy template context for Plane-Alert display templates."""

    def __init__(
        self,
        alert: PlaneAlert,
        position: int | None,
    ) -> None:
        """Create a Plane-Alert template context.

        Args:
            alert: Plane-Alert record used to populate requested variables.
            position: Optional one-based alert position for lower detail rows.
        """
        super().__init__()
        self._alert = alert
        self._position = position

    def __missing__(self, key: str) -> Any:
        value = _plane_alert_template_value(key, self._alert, self._position)
        self[key] = value
        return value


def build_plane_alert_template_text(
    template: str,
    alert: PlaneAlert,
    position: int | None = None,
) -> str:
    """Build Plane-Alert display text from a configured template.

    Args:
        template: Python ``str.format_map``-style template containing
            Plane-Alert variable names in braces.
        alert: Plane-Alert record used to populate template variables.
        position: Optional one-based alert position for lower detail rows.

    Returns:
        Rendered display text with unknown variables converted to blank text.
    """
    try:
        return template.format_map(
            _PlaneAlertTemplateContext(alert, position),
        ).strip()
    except (KeyError, TypeError, ValueError):
        return ""


def _plane_alert_template_value(
    key: str,
    alert: PlaneAlert,
    position: int | None,
) -> Any:
    match key:
        case "hex":
            return alert.hex.upper()
        case "tail":
            return alert.tail
        case "tail_or_hex":
            return alert.tail or alert.hex.upper()
        case "call":
            return alert.call.removeprefix("@")
        case "display_name":
            return alert.display_name
        case "name":
            return alert.name
        case "owner":
            return alert.name
        case "equipment":
            return alert.equipment
        case "aircraft_type":
            return alert.equipment
        case "timestamp":
            if alert.timestamp is None:
                return ""
            return alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        case "time":
            return format_plane_alert_timestamp(alert.timestamp)
        case "date_time":
            if alert.timestamp is None:
                return ""
            return alert.timestamp.strftime("%d %b %H:%M")
        case "latitude":
            return "" if alert.lat is None else f"{alert.lat:.3f}"
        case "longitude":
            return "" if alert.lon is None else f"{alert.lon:.3f}"
        case "position":
            return position or ""
        case "position_ordinal":
            return _ordinal_text(position) if position is not None else ""
        case "summary_left":
            return build_plane_alert_summary_left_text(alert)
        case "summary_right":
            return build_plane_alert_summary_right_text(alert)
        case "summary":
            return build_plane_alert_summary_text(alert)
        case "detail":
            return build_plane_alert_detail_text(alert)
        case "loop_alert":
            if position is None:
                return ""
            return build_plane_alert_loop_alert_text(alert, position)
        case "loop_info":
            return build_plane_alert_loop_info_text(alert)
        case "loop_time":
            return format_plane_alert_timestamp(alert.timestamp)
        case _:
            return ""


def build_plane_alert_summary_left_text(alert: PlaneAlert) -> str:
    """Build the left-side top-row summary for a Plane-Alert record."""
    return alert.display_name


def build_plane_alert_summary_right_text(alert: PlaneAlert) -> str:
    """Build the right-side top-row summary for a Plane-Alert record."""
    parts = [
        alert.tail or alert.hex.upper(),
        alert.equipment,
        format_plane_alert_timestamp(alert.timestamp),
    ]
    return "  ".join(part for part in parts if part)


def build_plane_alert_summary_text(alert: PlaneAlert) -> str:
    """Build the complete top-row summary for a Plane-Alert record."""
    return "    ".join(
        part
        for part in [
            build_plane_alert_summary_left_text(alert),
            build_plane_alert_summary_right_text(alert),
        ]
        if part
    )


def build_plane_alert_loop_alert_text(alert: PlaneAlert, position: int) -> str:
    """Build the lower-row left text for a secondary Plane-Alert record."""
    return "  ".join(
        part
        for part in [
            _ordinal_text(position),
            alert.display_name,
            alert.equipment,
        ]
        if part
    )


def build_plane_alert_loop_info_text(alert: PlaneAlert) -> str:
    """Build the lower-row right text for a secondary Plane-Alert record."""
    return "  ".join(
        part
        for part in [
            alert.tail or alert.hex.upper(),
            format_plane_alert_timestamp(alert.timestamp),
        ]
        if part
    )


def _ordinal_text(position: int | None) -> str:
    if position is None:
        return ""
    if 10 <= position % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
    return f"{position}{suffix}"


def build_plane_alert_detail_text(alert: PlaneAlert) -> str:
    """Build the scrolling detail line for a Plane-Alert record."""
    parts = [alert.equipment, alert.name]
    if alert.lat is not None and alert.lon is not None:
        parts.append(f"pos {alert.lat:.3f},{alert.lon:.3f}")
    if alert.timestamp is not None:
        parts.append(f"seen {alert.timestamp.strftime('%d %b %H:%M')}")
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
        timestamp=_parse_plane_alert_timestamp(item),
        lat=_optional_float(item.get("lat", item.get("latitude"))),
        lon=_optional_float(item.get("lon", item.get("longitude"))),
    )


def _parse_plane_alert_timestamp(item: Mapping[str, Any]) -> datetime | None:
    preferred_timestamp = _first_parsed_timestamp(
        item,
        "last_seen",
        "lastseen",
        "lastSeen",
        "seen",
        "updated",
        "updated_at",
        "timestamp",
        "time:time_at_mindist",
        "time_at_mindist",
        "time",
    )
    if preferred_timestamp is not None:
        return preferred_timestamp

    return _first_parsed_timestamp(item, "first_seen", "firstseen", "firstSeen")


def _first_parsed_timestamp(
    item: Mapping[str, Any],
    *keys: str,
) -> datetime | None:
    for key in keys:
        parsed = _parse_timestamp(_clean_text(item.get(key)))
        if parsed is not None:
            return parsed
    return None


def _passes_age_filter(
    alert: PlaneAlert,
    max_age_minutes: float | None,
    now: datetime | None,
) -> bool:
    if max_age_minutes is None or alert.timestamp is None:
        return True
    comparison_now = (now or datetime.now()).replace(tzinfo=None)
    return comparison_now - alert.timestamp <= timedelta(minutes=max_age_minutes)


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
