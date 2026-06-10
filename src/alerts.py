from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from plane_alert import (
    PlaneAlert,
    build_plane_alert_template_text,
    fetch_plane_alert_json,
    parse_plane_alerts,
)


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
            f"{self.source}:{plane_alert_identity(self.plane_alert)}:"
            f"{timestamp}"
        )


def plane_alert_identity(alert: PlaneAlert) -> str:
    """Return a stable identity for detecting newly added Plane-Alert rows.

    Args:
        alert: Plane-Alert row from the live table.

    Returns:
        Stable row identity. The live stream's zero-based ``index`` is preferred
        because it identifies newly appended table rows even when aircraft repeat.
    """
    if alert.index is not None:
        return f"index:{alert.index}"

    timestamp = alert.timestamp.isoformat() if alert.timestamp is not None else ""
    identity_parts = (
        alert.hex.upper(),
        alert.call.upper(),
        alert.tail.upper(),
        timestamp,
    )
    return "fields:" + "|".join(identity_parts)


def build_alert_template_text(template: str, alert: DisplayAlert) -> str:
    """Build full-screen alert text from a configured template.

    Args:
        template: Python ``str.format_map``-style template.
        alert: Display alert used to populate template variables.

    Returns:
        Rendered alert text, or an empty string for invalid templates.
    """
    try:
        return template.format_map(_AlertTemplateContext(alert)).strip()
    except (KeyError, TypeError, ValueError):
        return ""


class PlaneAlertListAlertListener:
    """Poll Plane-Alert history and alert when a new row appears."""

    def __init__(
        self,
        alert_config: Mapping[str, Any],
        plane_alert_config: Mapping[str, Any],
        load_alerts: Callable[[], Sequence[PlaneAlert]] | None = None,
    ) -> None:
        """Create a listener using Plane-Alert datasource configuration.

        Args:
            alert_config: The ``config["alerts"]`` mapping.
            plane_alert_config: The ``config["planeAlert"]`` mapping.
            load_alerts: Optional loader for tests. When omitted, the listener
                fetches and parses the configured Plane-Alert source URL.
        """
        self._alert_config = alert_config
        self._plane_alert_config = plane_alert_config
        self._load_alerts = load_alerts or self._load_plane_alert_rows
        self._events: queue.Queue[DisplayAlert] = queue.Queue(maxsize=10)
        self._seen_identities: set[str] = set()
        self._primed = False
        self._active_alert: DisplayAlert | None = None
        self._active_until = 0.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start polling Plane-Alert history in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="plane-alert-list-alerts",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the polling thread without blocking display shutdown."""
        self._stop_event.set()
        if self._thread is None:
            return
        self._thread.join(timeout=2.0)
        self._thread = None

    def poll_once(self) -> None:
        """Poll the Plane-Alert datasource once and queue any newly added row."""
        rows = list(self._load_alerts())
        identities = [plane_alert_identity(row) for row in rows]
        current_identities = set(identities)

        if not self._primed:
            self._seen_identities = current_identities
            self._primed = True
            return

        new_rows = [
            row
            for row, identity in zip(rows, identities, strict=True)
            if identity not in self._seen_identities
        ]
        self._seen_identities.update(current_identities)
        if not new_rows:
            return

        newest_new_row = new_rows[0]
        _put_drop_oldest(
            self._events,
            DisplayAlert(
                source=str(self._plane_alert_config["sourceUrl"]),
                received_at=datetime.now(timezone.utc).replace(tzinfo=None),
                plane_alert=newest_new_row,
            ),
        )

    def current_alert(self, now: float | None = None) -> DisplayAlert | None:
        """Return the active alert, promoting queued new rows as needed.

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

    def _poll_loop(self) -> None:
        poll_interval = float(self._alert_config["pollInterval"])
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except (OSError, ValueError, requests.RequestException) as err:
                print(f"Warning: Failed to poll Plane-Alert alerts: {err}")
            self._stop_event.wait(poll_interval)

    def _load_plane_alert_rows(self) -> list[PlaneAlert]:
        payload = fetch_plane_alert_json(
            str(self._plane_alert_config["sourceUrl"]),
            float(self._plane_alert_config["fetchTimeout"]),
            str(self._plane_alert_config["userAgent"]),
        )
        return parse_plane_alerts(
            payload,
            self._plane_alert_config["maxAgeHours"],
            int(self._plane_alert_config["displayCount"]),
        )

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
        self._active_until = now + float(self._alert_config["displayDuration"])


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
