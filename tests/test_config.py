from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from config import parse_display_modes  # noqa: E402


def test_parse_display_modes_defaults_to_train_only():
    assert parse_display_modes(None) == ["train"]


def test_parse_display_modes_accepts_explicit_train_only():
    assert parse_display_modes("train") == ["train"]


def test_parse_display_modes_filters_invalid_modes():
    assert parse_display_modes("train, invalid, plane, train") == ["train", "plane"]
