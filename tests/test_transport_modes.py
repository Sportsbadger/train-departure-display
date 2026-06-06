from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from transport_modes import (  # noqa: E402
    build_mode_state,
    parse_modes,
    update_mode_state,
)


def test_parse_modes_keeps_train_default_and_requires_adsb_enabled():
    assert parse_modes("adsb", adsb_enabled=False) == ["train"]
    assert parse_modes("adsb", adsb_enabled=True) == ["train", "adsb"]
    assert parse_modes("train,adsb,train", adsb_enabled=True) == ["train", "adsb"]


def test_update_mode_state_switches_after_interval():
    modes = ["train", "adsb"]
    state = build_mode_state(modes, now=0.0)

    update_mode_state(state, modes, now=299.0, switch_interval_s=300.0)
    assert state.active_mode == "train"

    update_mode_state(state, modes, now=300.0, switch_interval_s=300.0)
    assert state.active_mode == "adsb"

    update_mode_state(state, modes, now=600.0, switch_interval_s=300.0)
    assert state.active_mode == "train"
