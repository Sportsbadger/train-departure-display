from __future__ import annotations

import queue
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from plane_alert import PlaneAlert, build_plane_alert_template_text


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
    """Detect new rows from observed Plane-Alert datasource snapshots."""

    def __init__(self, alert_config: Mapping[str, Any]) -> None:
        """Create a listener using alert display configuration.

        Args:
            alert_config: The ``config["alerts"]`` mapping.
        """
        self._alert_config = alert_config
        self._events: queue.Queue[DisplayAlert] = queue.Queue(maxsize=10)
        self._seen_identities: set[str] = set()
        self._primed = False
        self._last_observed_signature: str | None = None
        self._active_alert: DisplayAlert | None = None
        self._active_until = 0.0

    def start(self) -> None:
        """Start the listener.

        The listener is intentionally passive: the main loop feeds it completed
        Plane-Alert cache snapshots so alerting adds no network thread or
        duplicate parser workload.
        """

    def stop(self) -> None:
        """Stop the listener.

        The passive listener owns no background resources.
        """

    def observe(
        self,
        rows: Sequence[PlaneAlert] | None,
        source: str,
        received_at: datetime | None = None,
    ) -> None:
        """Observe a completed Plane-Alert list and queue newly added rows.

        Args:
            rows: Newest-first Plane-Alert rows from the shared datasource cache.
            source: Source URL or label for alert templates.
            received_at: Optional receipt time for deterministic tests.
        """
        if rows is None:
            return

        identities = [plane_alert_identity(row) for row in rows]
        signature = "\n".join(identities)
        if signature == self._last_observed_signature:
            return

        self._last_observed_signature = signature
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

        _put_drop_oldest(
            self._events,
            DisplayAlert(
                source=source,
                received_at=received_at
                or datetime.now(timezone.utc).replace(tzinfo=None),
                plane_alert=new_rows[0],
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
