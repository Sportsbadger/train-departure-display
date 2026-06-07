from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ModeState:
    """Tracks the active transport mode and last switch time."""

    active_mode: str
    last_switch: float


def parse_modes(
    raw_modes: str,
    adsb_enabled: bool,
    plane_alert_enabled: bool = False,
    alerts_enabled: bool = False,
) -> list[str]:
    """Parse configured transport modes.

    Args:
        raw_modes: Comma-separated transport mode names.
        adsb_enabled: Whether ADS-B mode is allowed.
        plane_alert_enabled: Whether Plane-Alert mode is allowed.
        alerts_enabled: Whether the interrupt-only alerts overlay is allowed.

    Returns:
        Ordered, de-duplicated cyclic mode names. The ``alerts`` token is
        accepted for configuration readability but is not returned because
        alerts interrupt the active mode instead of consuming a rotation slot.
    """
    allowed = {"train"}
    if adsb_enabled:
        allowed.add("adsb")
    if plane_alert_enabled:
        allowed.add("plane-alert")
        allowed.add("planealert")
    modes: list[str] = []
    for raw_mode in raw_modes.split(","):
        mode = raw_mode.strip().lower()
        if mode == "planealert":
            mode = "plane-alert"
        if mode == "alerts" and alerts_enabled:
            continue
        if not mode or mode not in allowed or mode in modes:
            continue
        modes.append(mode)

    if modes:
        return modes
    return ["train"]


def build_mode_state(modes: Sequence[str], now: float) -> ModeState:
    """Build initial mode state from available modes."""
    if not modes:
        return ModeState(active_mode="train", last_switch=now)
    return ModeState(active_mode=modes[0], last_switch=now)


def update_mode_state(
    state: ModeState,
    modes: Sequence[str],
    now: float,
    switch_interval_s: float,
) -> None:
    """Switch to the next configured mode when the interval has elapsed."""
    if len(modes) < 2:
        state.active_mode = modes[0] if modes else "train"
        state.last_switch = now
        return
    if now - state.last_switch < switch_interval_s:
        return

    try:
        current_index = modes.index(state.active_mode)
    except ValueError:
        current_index = 0

    state.active_mode = modes[(current_index + 1) % len(modes)]
    state.last_switch = now
