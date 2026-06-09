from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from transport_modes import (  # noqa: E402
    advance_mode_item,
    build_mode_state,
    current_item_index,
    parse_modes,
    should_rebuild_mode_viewport,
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


def test_update_mode_state_switches_after_interval_and_resets_item():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)
    state.item_index = 3
    state.completed_runs = 2

    assert (
        update_mode_state(state, modes, now=299.0, switch_interval_s=300.0)
        is False
    )
    assert state.active_mode == "train"

    assert (
        update_mode_state(state, modes, now=300.0, switch_interval_s=300.0)
        is True
    )
    assert state.active_mode == "adsb"
    assert state.item_index == 0
    assert state.completed_runs == 0

    assert (
        update_mode_state(state, modes, now=600.0, switch_interval_s=300.0)
        is True
    )
    assert state.active_mode == "train"


def test_update_mode_state_does_not_switch_without_interval_override():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)

    assert (
        update_mode_state(state, modes, now=999.0, switch_interval_s=None)
        is False
    )
    assert state.active_mode == "train"


def test_advance_mode_item_switches_after_configured_full_runs():
    modes = ["adsb", "train"]
    state = build_mode_state(modes, now=0.0)

    for expected_index in [1, 2, 0, 1, 2]:
        assert advance_mode_item(
            state,
            modes,
            item_count=3,
            run_count=2,
            now=10.0,
        ) is False
        assert state.active_mode == "adsb"
        assert state.item_index == expected_index

    assert advance_mode_item(
        state,
        modes,
        item_count=3,
        run_count=2,
        now=12.0,
    ) is True
    assert state.active_mode == "train"
    assert state.item_index == 0
    assert state.completed_runs == 0


def test_advance_mode_item_interval_override_disables_run_count_switching():
    modes = ["adsb", "train"]
    state = build_mode_state(modes, now=0.0)

    assert advance_mode_item(
        state,
        modes,
        item_count=1,
        run_count=1,
        now=10.0,
        switch_interval_s=300.0,
    ) is False
    assert state.active_mode == "adsb"
    assert state.item_index == 0
    assert state.completed_runs == 1


def test_current_item_index_clamps_to_available_items():
    state = build_mode_state(["adsb"], now=0.0)
    state.item_index = 12

    assert current_item_index(state, item_count=5) == 2
    assert current_item_index(state, item_count=0) == 0


def test_should_rebuild_mode_viewport_keeps_loaded_aircraft_animation_alive():
    assert should_rebuild_mode_viewport(
        "adsb",
        has_rendered_viewport=True,
        has_display_items=True,
        refresh_due=True,
    ) is False
    assert should_rebuild_mode_viewport(
        "plane-alert",
        has_rendered_viewport=True,
        has_display_items=True,
        refresh_due=True,
    ) is False


def test_should_rebuild_mode_viewport_retries_loading_and_non_animated_modes():
    assert should_rebuild_mode_viewport(
        "adsb",
        has_rendered_viewport=True,
        has_display_items=False,
        refresh_due=True,
    ) is True
    assert should_rebuild_mode_viewport(
        "adsb",
        has_rendered_viewport=False,
        has_display_items=True,
        refresh_due=True,
    ) is True
    assert should_rebuild_mode_viewport(
        "train",
        has_rendered_viewport=True,
        has_display_items=True,
        refresh_due=True,
    ) is True
    assert should_rebuild_mode_viewport(
        "train",
        has_rendered_viewport=True,
        has_display_items=True,
        refresh_due=False,
    ) is False


def test_should_rebuild_mode_viewport_rebuilds_when_loading_receives_items():
    assert should_rebuild_mode_viewport(
        "adsb",
        has_rendered_viewport=False,
        has_display_items=True,
        refresh_due=False,
    ) is True
    assert should_rebuild_mode_viewport(
        "plane-alert",
        has_rendered_viewport=False,
        has_display_items=True,
        refresh_due=False,
    ) is True
