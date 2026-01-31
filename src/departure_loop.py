from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

Departure = dict[str, str]


@dataclass
class LoopState:
    """Tracks looping state for secondary departures."""

    departures: list[Departure]
    index: int = 0
    last_update: float = 0.0


def ordinal(value: int) -> str:
    """Return the ordinal suffix representation for a positive integer."""
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def build_loop_state(
    departures: Sequence[Departure],
    loop_count: int,
    now: float,
) -> LoopState:
    """Build loop state from a departures list, skipping the first item."""
    loop_departures = list(departures[1 : 1 + loop_count])
    return LoopState(departures=loop_departures, index=0, last_update=now)


def advance_loop_index(index: int, length: int, step: int = 2) -> int:
    """Advance the loop index, wrapping around when needed."""
    if length <= 0:
        return 0
    return (index + step) % length


def update_loop_state(state: LoopState, now: float, interval_s: float) -> None:
    """Update the loop state index based on the interval."""
    if not state.departures:
        return
    if now - state.last_update >= interval_s:
        state.index = advance_loop_index(state.index, len(state.departures))
        state.last_update = now


def get_looped_departures(
    loop_departures: Sequence[Departure],
    start_index: int,
    window: int = 2,
) -> list[tuple[int, Departure]]:
    """Return up to window departures, with positions relative to original list."""
    if not loop_departures:
        return []
    start = start_index % len(loop_departures)
    results: list[tuple[int, Departure]] = []
    for offset in range(window):
        idx = start + offset
        if idx >= len(loop_departures):
            break
        results.append((idx + 2, loop_departures[idx]))
    return results
