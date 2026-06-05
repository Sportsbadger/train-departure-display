"""Bounded ADS-B JSON polling source."""

from __future__ import annotations

import time
from typing import Any, Mapping

import requests

from adsb import Aircraft, parse_aircraft_payload


class ADSBDataSource:
    """Poll decoded ADS-B JSON and keep the last successful aircraft snapshot."""

    def __init__(
        self,
        url: str,
        refresh_s: float,
        connect_timeout_s: float,
        read_timeout_s: float,
    ) -> None:
        """Initialize the data source.

        Args:
            url: Decoded readsb/tar1090 aircraft JSON URL.
            refresh_s: Minimum seconds between network polls.
            connect_timeout_s: Requests connect timeout in seconds.
            read_timeout_s: Requests read timeout in seconds.
        """
        self.url = url
        self.refresh_s = max(1.0, refresh_s)
        self.connect_timeout_s = max(0.1, connect_timeout_s)
        self.read_timeout_s = max(0.1, read_timeout_s)
        self.aircraft: list[Aircraft] = []
        self.last_error = ""
        self.last_poll_monotonic = -self.refresh_s

    def poll_if_due(self, now_monotonic: float | None = None) -> None:
        """Poll the source only when the refresh interval has elapsed.

        Args:
            now_monotonic: Optional monotonic timestamp for deterministic tests.
        """
        now = time.monotonic() if now_monotonic is None else now_monotonic
        if now - self.last_poll_monotonic < self.refresh_s:
            return
        self.last_poll_monotonic = now
        self.poll()

    def poll(self) -> None:
        """Poll the source immediately.

        The last valid aircraft list is retained on transient request or JSON
        validation failures so callers can keep rendering stale-but-known data.
        """
        try:
            response = requests.get(
                self.url,
                timeout=(self.connect_timeout_s, self.read_timeout_s),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("ADS-B JSON root must be an object")
            self.aircraft = parse_aircraft_payload(payload)
            self.last_error = ""
        except (requests.RequestException, ValueError) as err:
            self.last_error = str(err)

    def snapshot(self) -> tuple[list[Aircraft], str]:
        """Return cached aircraft and the latest source error.

        Returns:
            A copy of the cached aircraft list plus the latest error string.
        """
        return list(self.aircraft), self.last_error


def build_adsb_json_url(config: dict[str, Any]) -> str:
    """Build the ADS-B aircraft JSON URL from application config.

    Args:
        config: Loaded application config containing an ``adsb`` section.

    Returns:
        Configured aircraft JSON URL.

    Raises:
        ValueError: If neither ``adsbJsonUrl`` nor ``adsbHost`` is set.
    """
    adsb_config = config["adsb"]
    explicit_url = adsb_config.get("jsonUrl")
    if explicit_url:
        return str(explicit_url)

    host = adsb_config.get("host")
    if not host:
        raise ValueError("adsbJsonUrl or adsbHost must be set for ADS-B")

    port = int(adsb_config.get("jsonPort") or 80)
    path = str(adsb_config.get("jsonPath") or "/tar1090/data/aircraft.json")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{host}:{port}{path}"
