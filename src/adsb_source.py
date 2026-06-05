from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import requests

from adsb import Aircraft, parse_aircraft_payload


@dataclass
class ADSBDataSource:
    """Polls decoded ADS-B aircraft JSON with bounded network timeouts."""

    url: str
    refresh_s: float
    connect_timeout_s: float
    read_timeout_s: float
    last_poll_monotonic: float = 0.0
    last_error: str = ""
    aircraft: list[Aircraft] = field(default_factory=list)

    def poll_if_due(self, now: float | None = None) -> bool:
        """Poll the source when the refresh interval has elapsed.

        Args:
            now: Optional monotonic timestamp for tests.

        Returns:
            ``True`` when a poll was attempted, otherwise ``False``.
        """
        current = time.monotonic() if now is None else now
        if self.last_poll_monotonic and current - self.last_poll_monotonic < self.refresh_s:
            return False

        self.last_poll_monotonic = current
        self.poll()
        return True

    def poll(self) -> None:
        """Fetch aircraft JSON and update the cached aircraft list.

        Raises are intentionally contained so display refresh cannot be killed by
        a transient ADS-B feeder outage.
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
        """Return cached aircraft and the latest source error."""
        return list(self.aircraft), self.last_error


def build_adsb_json_url(config: dict[str, Any]) -> str:
    """Build the ADS-B JSON URL from config values.

    Args:
        config: Loaded application config.

    Returns:
        Configured aircraft JSON URL.

    Raises:
        ValueError: If plane mode is enabled without a usable URL or host.
    """
    adsb_config = config["adsb"]
    explicit_url = adsb_config.get("jsonUrl")
    if explicit_url:
        return str(explicit_url)

    host = adsb_config.get("host")
    if not host:
        raise ValueError("adsbJsonUrl or adsbHost must be set for plane mode")

    port = int(adsb_config.get("jsonPort") or 80)
    path = str(adsb_config.get("jsonPath") or "/tar1090/data/aircraft.json")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{host}:{port}{path}"
