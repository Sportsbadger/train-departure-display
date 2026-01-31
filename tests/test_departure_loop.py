from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from departure_loop import (  # noqa: E402
    advance_loop_index,
    build_loop_state,
    get_looped_departures,
    ordinal,
    update_loop_state,
)


def test_ordinal_suffixes():
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(4) == "4th"
    assert ordinal(11) == "11th"
    assert ordinal(12) == "12th"
    assert ordinal(13) == "13th"
    assert ordinal(21) == "21st"


def test_get_looped_departures_window():
    departures = [
        {"id": "first"},
        {"id": "second"},
        {"id": "third"},
        {"id": "fourth"},
    ]
    loop_state = build_loop_state(departures, loop_count=3, now=0.0)
    result = get_looped_departures(loop_state.departures, start_index=0)
    assert [(pos, dep["id"]) for pos, dep in result] == [
        (2, "second"),
        (3, "third"),
    ]


def test_get_looped_departures_wraps_and_truncates():
    departures = [
        {"id": "first"},
        {"id": "second"},
        {"id": "third"},
    ]
    loop_state = build_loop_state(departures, loop_count=2, now=0.0)
    result = get_looped_departures(loop_state.departures, start_index=1)
    assert [(pos, dep["id"]) for pos, dep in result] == [
        (3, "third"),
    ]


def test_update_loop_state_advances_index():
    departures = [
        {"id": "first"},
        {"id": "second"},
        {"id": "third"},
        {"id": "fourth"},
    ]
    loop_state = build_loop_state(departures, loop_count=3, now=0.0)
    update_loop_state(loop_state, now=11.0, interval_s=10.0)
    assert loop_state.index == advance_loop_index(0, len(loop_state.departures))
