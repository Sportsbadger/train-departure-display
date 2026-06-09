from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class ModeState:
    """Tracks active mode, switch time, and item-cycle progress."""

    active_mode: str
    last_switch: float
    item_index: int = 0
    completed_runs: int = 0


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


def switch_to_next_mode(
    state: ModeState,
    modes: Sequence[str],
    now: float,
) -> bool:
    """Switch state to the next mode and reset item progress.

    Args:
        state: Mutable mode state.
        modes: Ordered cyclic transport modes.
        now: Monotonic timestamp for the switch.

    Returns:
        True when the active mode changed, otherwise False.
    """
    if len(modes) < 2:
        next_mode = modes[0] if modes else "train"
        changed = state.active_mode != next_mode
        state.active_mode = next_mode
        state.last_switch = now
        state.item_index = 0
        state.completed_runs = 0
        return changed

    try:
        current_index = modes.index(state.active_mode)
    except ValueError:
        current_index = 0

    state.active_mode = modes[(current_index + 1) % len(modes)]
    state.last_switch = now
    state.item_index = 0
    state.completed_runs = 0
    return True


def update_mode_state(
    state: ModeState,
    modes: Sequence[str],
    now: float,
    switch_interval_s: float | None,
) -> bool:
    """Switch to the next configured mode when an interval is configured.

    Args:
        state: Mutable mode state.
        modes: Ordered cyclic transport modes.
        now: Monotonic timestamp.
        switch_interval_s: Optional interval override. ``None`` disables
            time-based switching so item-cycle counts control transitions.

    Returns:
        True when the active mode changed, otherwise False.
    """
    if switch_interval_s is None:
        return False
    if now - state.last_switch < switch_interval_s:
        return False
    return switch_to_next_mode(state, modes, now)


def advance_mode_item(
    state: ModeState,
    modes: Sequence[str],
    item_count: int,
    run_count: int,
    now: float,
    switch_interval_s: float | None = None,
) -> bool:
    """Advance the active mode's item pointer and switch after run_count loops.

    Args:
        state: Mutable mode state.
        modes: Ordered cyclic transport modes.
        item_count: Number of displayable items in the active mode.
        run_count: Number of full item-list runs before switching modes.
        now: Monotonic timestamp for a mode switch.
        switch_interval_s: Optional time-based switch interval. When set,
            item advancement still happens, but run-count mode switching is
            disabled because the interval is the override.

    Returns:
        True when the active mode changed, otherwise False.
    """
    safe_item_count = max(1, item_count)
    safe_run_count = max(1, run_count)
    next_item_index = state.item_index + 1

    if next_item_index < safe_item_count:
        state.item_index = next_item_index
        return False

    state.item_index = 0
    state.completed_runs += 1
    if switch_interval_s is not None or state.completed_runs < safe_run_count:
        return False

    return switch_to_next_mode(state, modes, now)


def current_item_index(state: ModeState, item_count: int) -> int:
    """Return the active item index clamped to available items."""
    if item_count <= 0:
        return 0
    return state.item_index % item_count
