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


def mode_cycle_duration_s(
    item_count: int,
    mode_cycle_count: int,
    item_interval_s: float,
) -> float:
    """Return the time a mode should run before cycle-based switching.

    Args:
        item_count: Number of display items in the active mode.
        mode_cycle_count: Number of complete item-list cycles to show.
        item_interval_s: Seconds each display item is expected to remain visible.

    Returns:
        Positive mode duration in seconds. Empty modes are treated as one
        placeholder item so loading/unavailable screens still rotate.
    """
    safe_item_count = max(1, item_count)
    safe_cycle_count = max(1, mode_cycle_count)
    safe_item_interval_s = max(1.0, item_interval_s)
    return safe_item_count * safe_cycle_count * safe_item_interval_s


def update_mode_state(
    state: ModeState,
    modes: Sequence[str],
    now: float,
    switch_interval_s: float | None,
    mode_cycle_count: int = 1,
    active_mode_item_count: int = 1,
    item_interval_s: float = 1.0,
) -> None:
    """Switch to the next configured mode when the active run completes.

    Args:
        state: Mutable mode state to update.
        modes: Ordered transport modes.
        now: Current monotonic timestamp.
        switch_interval_s: Optional absolute override in seconds. When set,
            this preserves legacy time-based mode switching.
        mode_cycle_count: Number of complete item-list cycles per mode.
        active_mode_item_count: Number of items in the active mode.
        item_interval_s: Seconds allocated to each item for cycle switching.
    """
    if len(modes) < 2:
        state.active_mode = modes[0] if modes else "train"
        state.last_switch = now
        return

    if switch_interval_s is None:
        switch_after_s = mode_cycle_duration_s(
            active_mode_item_count,
            mode_cycle_count,
            item_interval_s,
        )
    else:
        switch_after_s = switch_interval_s

    if now - state.last_switch < switch_after_s:
        return

    try:
        current_index = modes.index(state.active_mode)
    except ValueError:
        current_index = 0

    state.active_mode = modes[(current_index + 1) % len(modes)]
    state.last_switch = now
