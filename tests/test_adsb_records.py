from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import AdsbAircraft  # noqa: E402
from adsb_records import (  # noqa: E402
    build_record_summary_text,
    load_adsb_record_boards,
    update_adsb_record_store,
)


def aircraft(
    hex_value: str,
    label: str,
    altitude_ft: int | None,
    speed_kt: int | None,
    distance_nm: float,
    vertical_rate_fpm: int | None = None,
) -> AdsbAircraft:
    return AdsbAircraft(
        hex=hex_value,
        flight=label,
        latitude=51.0,
        longitude=-0.1,
        distance_nm=distance_nm,
        bearing_deg=90,
        altitude_ft=altitude_ft,
        ground_speed_kt=speed_kt,
        true_air_speed_kt=None,
        mach=None,
        track_deg=180,
        vertical_rate_fpm=vertical_rate_fpm,
        squawk="",
        aircraft_type="A320",
        registration="",
        description="",
        seen_seconds=1.0,
    )


def test_update_adsb_record_store_builds_rolling_and_forever_records(tmp_path):
    store_path = tmp_path / "adsb-records.json"

    boards = update_adsb_record_store(
        store_path,
        [
            aircraft("aaa111", "LOW1", 2_000, 150, 2.5, -500),
            aircraft("bbb222", "HIGH1", 39_000, 480, 44.2, 1_600),
        ],
        now=1_000_000.0,
    )

    day = boards[0]
    assert day.window == "day"
    assert day.observation_count == 2
    assert day.records[0].metric == "highest"
    assert day.records[0].aircraft_label == "HIGH1"
    assert day.records[2].metric == "fastest"
    assert day.records[2].value == 480
    assert "Furthest 44.2nm HIGH1" in build_record_summary_text(day)

    update_adsb_record_store(
        store_path,
        [aircraft("ccc333", "OLDER", 45_000, 510, 90.0)],
        now=1_000_000.0 - (8 * 24 * 60 * 60),
    )

    reloaded = load_adsb_record_boards(store_path, now=1_000_000.0)
    forever = reloaded[2]
    assert forever.window == "forever"
    assert forever.records[0].aircraft_label == "OLDER"
    assert forever.records[4].aircraft_label == "OLDER"
