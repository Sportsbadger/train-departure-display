from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from transport_modes import (  # noqa: E402
    build_mode_state,
    mode_cycle_duration_s,
    parse_modes,
    update_mode_state,
)


def test_parse_modes_respects_explicit_adsb_only_mode():
    assert parse_modes("adsb", adsb_enabled=False) == ["train"]
    assert parse_modes("adsb", adsb_enabled=True) == ["adsb"]
    assert parse_modes("train,adsb,train", adsb_enabled=True) == ["train", "adsb"]
    assert parse_modes("", adsb_enabled=True) == ["train"]


def test_parse_modes_respects_explicit_plane_alert_mode():
    assert parse_modes("plane-alert", adsb_enabled=False) == ["train"]
    assert parse_modes(
        "train,planealert,adsb",
        adsb_enabled=True,
        plane_alert_enabled=True,
    ) == ["train", "plane-alert", "adsb"]


def test_parse_modes_accepts_alerts_as_interrupt_only_overlay():
    assert parse_modes(
        "train,adsb,plane-alert,alerts",
        adsb_enabled=True,
        plane_alert_enabled=True,
        alerts_enabled=True,
    ) == ["train", "adsb", "plane-alert"]


def test_update_mode_state_switches_after_interval():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)

    update_mode_state(state, modes, now=299.0, switch_interval_s=300.0)
    assert state.active_mode == "train"

    update_mode_state(state, modes, now=300.0, switch_interval_s=300.0)
    assert state.active_mode == "adsb"

    update_mode_state(state, modes, now=600.0, switch_interval_s=300.0)
    assert state.active_mode == "train"


def test_mode_cycle_duration_counts_items_and_cycles():
    assert mode_cycle_duration_s(10, 2, 12.5) == 250.0
    assert mode_cycle_duration_s(0, 0, 0.1) == 1.0


def test_update_mode_state_switches_after_cycle_count_without_interval():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)

    update_mode_state(
        state,
        modes,
        now=59.0,
        switch_interval_s=None,
        mode_cycle_count=2,
        active_mode_item_count=3,
        item_interval_s=10.0,
    )
    assert state.active_mode == "train"

    update_mode_state(
        state,
        modes,
        now=60.0,
        switch_interval_s=None,
        mode_cycle_count=2,
        active_mode_item_count=3,
        item_interval_s=10.0,
    )
    assert state.active_mode == "adsb"


def test_update_mode_state_interval_overrides_cycle_count():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)

    update_mode_state(
        state,
        modes,
        now=59.0,
        switch_interval_s=60.0,
        mode_cycle_count=10,
        active_mode_item_count=10,
        item_interval_s=10.0,
    )
    assert state.active_mode == "train"

    update_mode_state(
        state,
        modes,
        now=60.0,
        switch_interval_s=60.0,
        mode_cycle_count=10,
        active_mode_item_count=10,
        item_interval_s=10.0,
    )
    assert state.active_mode == "adsb"
