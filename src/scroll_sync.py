from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrollCompletion:
    """Tracks render-driven completion of repeated scroll cycles."""

    required_cycles: int = 2
    completed_cycles: int = 0
    complete: bool = False

    def __post_init__(self) -> None:
        """Normalize the required cycle count after initialization."""
        self.required_cycles = max(1, self.required_cycles)

    def mark_cycle_complete(self) -> None:
        """Record one fully exited scroll cycle."""
        if self.complete:
            return
        self.completed_cycles += 1
        self.complete = self.completed_cycles >= self.required_cycles
