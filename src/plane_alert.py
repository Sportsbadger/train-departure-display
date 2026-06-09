from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

LAST_LINE_TEXT = "****Last Line****"

TIMESTAMP_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)

CSV_FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "hex": ("hex", "icao", "icao24", "icao_hex", "icao id", "hex id"),
    "tail": (
        "tail",
        "tail_number",
        "registration",
        "reg",
        "n-number",
    ),
    "call": ("call", "callsign", "flight", "flight number"),
    "name": ("name", "owner", "owner_name", "operator"),
    "equipment": (
        "equipment",
        "type",
        "aircraft_type",
        "aircraft type",
        "make/model",
        "description",
    ),
    "timestamp": (
        "timestamp",
        "first_seen",
        "last_seen",
        "time:time_at_mindist",
        "time_at_mindist",
        "time",
        "date/time",
        "datetime",
    ),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "longitude", "lng"),
}

JSON_WRAPPER_KEYS = (
    "data",
    "records",
    "alerts",
    "plane_alert",
    "plane-alert",
    "aaData",
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
    """Fetch Plane-Alert API data from docker-planefence.

    The documented Plane-Alert endpoint is ``/plane-alert/pa_query.php`` and
    supports ``type=json`` and ``type=csv`` query output. This function keeps
    the historic name for compatibility but deliberately accepts either JSON or
    CSV responses because some deployments/proxies return CSV even when the URL
    was configured manually.

    Args:
        source_url: HTTP URL for ``pa_query.php`` including query parameters.
        timeout_s: Maximum request time in seconds.
        user_agent: HTTP User-Agent header for reverse proxies.

    Returns:
        Decoded JSON data, or a list of dictionaries decoded from CSV.

    Raises:
        requests.RequestException: If the HTTP request fails or times out.
        PlaneAlertDataError: If the response is neither JSON nor valid CSV.
    """
    headers = {
        "Accept": "application/json, text/csv;q=0.9, */*;q=0.1",
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": user_agent,
    }
    response = requests.get(
        ensure_plane_alert_api_url(source_url),
        headers=headers,
        timeout=timeout_s,
    )
    response.raise_for_status()
    if hasattr(response, "text"):
        return decode_plane_alert_response(
            response.text,
            getattr(response, "status_code", None),
        )

    try:
        return response.json()
    except ValueError as err:
        raise PlaneAlertDataError("Plane-Alert response was not JSON") from err


def ensure_plane_alert_api_url(source_url: str) -> str:
    """Return a Plane-Alert API URL with an explicit ``type=json`` parameter.

    Args:
        source_url: Configured Plane-Alert API URL.

    Returns:
        URL with ``type=json`` added when no ``type`` query parameter exists.
    """
    split_url = urlsplit(source_url)
    query_items = parse_qsl(split_url.query, keep_blank_values=True)
    if any(key.lower() == "type" for key, _value in query_items):
        return source_url

    query_items.append(("type", "json"))
    return urlunsplit(
        (
            split_url.scheme,
            split_url.netloc,
            split_url.path,
            urlencode(query_items),
            split_url.fragment,
        ),
    )


def decode_plane_alert_response(text: str, status_code: int | None = None) -> Any:
    """Decode a Plane-Alert response body as JSON, then CSV fallback.

    Args:
        text: HTTP response body.
        status_code: Optional HTTP status for error messages.

    Returns:
        Decoded JSON value, or CSV records as dictionaries.

    Raises:
        PlaneAlertDataError: If response body cannot be decoded.
    """
    stripped = text.lstrip("\ufeff").strip()
    if not stripped:
        return []

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as json_err:
        csv_records = _parse_csv_records(stripped)
        if csv_records is not None:
            return csv_records

        body_preview = stripped[:120] or "<empty response>"
        status_text = f"HTTP {status_code}: " if status_code is not None else ""
        raise PlaneAlertDataError(
            f"Plane-Alert response was not JSON or CSV ({status_text}{body_preview})",
        ) from json_err


def parse_plane_alerts(
    payload: Any,
    max_age_hours: float | None,
    limit: int,
    now: datetime | None = None,
) -> list[PlaneAlert]:
    """Parse, filter, de-duplicate, and sort Plane-Alert records newest-first.

    Args:
        payload: Decoded ``pa_query.php`` JSON/CSV payload.
        max_age_hours: Optional maximum alert age in hours.
        limit: Maximum number of alerts to return.
        now: Optional current time used by tests.

    Returns:
        Latest matching Plane-Alert records.

    Raises:
        PlaneAlertDataError: If the payload shape is unsupported.
    """
    if limit <= 0:
        return []

    records = _extract_records(payload)
    alerts = [
        parsed
        for item in records
        for parsed in [_coerce_plane_alert_item(item)]
        if parsed is not None
    ]
    filtered = [
        alert
        for alert in _dedupe_alerts(alerts)
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


def build_plane_alert_summary_left_text(alert: PlaneAlert) -> str:
    """Build the left-side top-row summary for a Plane-Alert record."""
    return "  ".join(
        part
        for part in [
            alert.display_name,
            alert.tail or alert.hex.upper(),
            format_plane_alert_timestamp(alert.timestamp),
        ]
        if part
    )


def build_plane_alert_summary_text(alert: PlaneAlert) -> str:
    """Build the complete top-row summary for a Plane-Alert record."""
    return "    ".join(
        part
        for part in [
            build_plane_alert_summary_left_text(alert),
            alert.hex.upper(),
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
            alert.tail,
        ]
        if part
    )


def build_plane_alert_loop_info_text(alert: PlaneAlert) -> str:
    """Build the lower-row right text for a secondary Plane-Alert record."""
    return "  ".join(
        part
        for part in [
            alert.equipment or alert.name,
            format_plane_alert_timestamp(alert.timestamp),
        ]
        if part
    )


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
            return alert.hex.upper() or "------"
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


def _extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        raise PlaneAlertDataError("Plane-Alert response must be a JSON list or object")

    for key in JSON_WRAPPER_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    if all(isinstance(value, Mapping) for value in payload.values()):
        return list(payload.values())

    raise PlaneAlertDataError("Plane-Alert response must contain a records list")


def _coerce_plane_alert_item(item: Any) -> PlaneAlert | None:
    if isinstance(item, Mapping):
        return _parse_plane_alert_mapping(item)
    if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
        return _parse_plane_alert_sequence(item)
    return None


def _parse_plane_alert_mapping(item: Mapping[str, Any]) -> PlaneAlert | None:
    normalized = {_normalize_header(key): value for key, value in item.items()}
    hex_value = _first_clean_text(normalized, *CSV_FIELD_ALIASES["hex"])
    tail = _first_clean_text(normalized, *CSV_FIELD_ALIASES["tail"])
    call = _first_clean_text(normalized, *CSV_FIELD_ALIASES["call"])
    if not any((hex_value, tail, call)):
        return None

    return PlaneAlert(
        hex=hex_value.upper(),
        tail=tail,
        call=call,
        name=_first_clean_text(normalized, *CSV_FIELD_ALIASES["name"]),
        equipment=_first_clean_text(
            normalized,
            *CSV_FIELD_ALIASES["equipment"],
        ),
        timestamp=_parse_timestamp(
            _first_clean_text(normalized, *CSV_FIELD_ALIASES["timestamp"]),
        ),
        lat=_optional_float(_first_value(normalized, *CSV_FIELD_ALIASES["lat"])),
        lon=_optional_float(_first_value(normalized, *CSV_FIELD_ALIASES["lon"])),
    )


def _parse_plane_alert_sequence(item: Sequence[Any]) -> PlaneAlert | None:
    values = [_clean_text(value) for value in item]
    if len(values) < 3:
        return None

    # DataTables/legacy exports have used positional rows. The documented
    # columns are hex, tail, name, equipment, timestamp, call, lat, lon.
    padded = values + [""] * 8
    record = {
        "hex": padded[0],
        "tail": padded[1],
        "name": padded[2],
        "equipment": padded[3],
        "timestamp": padded[4],
        "call": padded[5],
        "lat": padded[6],
        "lon": padded[7],
    }
    return _parse_plane_alert_mapping(record)


def _dedupe_alerts(alerts: Iterable[PlaneAlert]) -> list[PlaneAlert]:
    deduped: dict[tuple[str, str, str], PlaneAlert] = {}
    for alert in alerts:
        key = (
            alert.hex.upper(),
            alert.call.upper(),
            alert.timestamp.isoformat() if alert.timestamp is not None else "",
        )
        existing = deduped.get(key)
        if existing is None or _field_score(alert) > _field_score(existing):
            deduped[key] = alert
    return list(deduped.values())


def _field_score(alert: PlaneAlert) -> int:
    return sum(
        1
        for value in (
            alert.hex,
            alert.tail,
            alert.call,
            alert.name,
            alert.equipment,
            alert.timestamp,
            alert.lat,
            alert.lon,
        )
        if value not in (None, "")
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
        return datetime.fromtimestamp(
            int(value),
            tz=timezone.utc,
        ).replace(tzinfo=None)
    for date_format in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
            tzinfo=None,
        )
    except ValueError:
        return None


def _parse_csv_records(text: str) -> list[dict[str, str]] | None:
    if "<html" in text[:100].lower():
        return None
    sample = text[:2048]
    if "," not in sample and ";" not in sample and "\t" not in sample:
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    stream = io.StringIO(text.lstrip("\ufeff"), newline="")
    try:
        reader = csv.DictReader(stream, dialect=dialect)
        if reader.fieldnames is None:
            return None
        fieldnames = [_normalize_header(name) for name in reader.fieldnames]
        if not _looks_like_plane_alert_headers(fieldnames):
            return None

        records: list[dict[str, str]] = []
        for row in reader:
            if row is None:
                continue
            normalized_row = {
                _normalize_header(key): _clean_text(value)
                for key, value in row.items()
                if key is not None
            }
            if any(normalized_row.values()):
                records.append(normalized_row)
        return records
    except csv.Error:
        return None


def _looks_like_plane_alert_headers(fieldnames: Sequence[str]) -> bool:
    header_set = set(fieldnames)
    return any(alias in header_set for alias in CSV_FIELD_ALIASES["hex"]) and any(
        alias in header_set for alias in CSV_FIELD_ALIASES["timestamp"]
    )


def _first_clean_text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = _clean_text(item.get(_normalize_header(key)))
        if text:
            return text
    return ""


def _first_value(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(_normalize_header(key))
        if value not in (None, ""):
            return value
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value: Any) -> str:
    return _clean_text(value).lstrip("\ufeff").lower().replace("_", " ").strip()


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ordinal_text(position: int | None) -> str:
    if position is None:
        return ""
    if 10 <= position % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
    return f"{position}{suffix}"
