from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import AdsbAircraft  # noqa: E402
from adsb_records import (  # noqa: E402
    AdsbRecordBoard,
    AdsbMetricRecord,
    build_record_summary_text,
    load_adsb_record_boards,
    record_mode_entry_count,
    select_record_display_page,
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


def metric_record(metric: str, value: float) -> AdsbMetricRecord:
    return AdsbMetricRecord(
        metric=metric,
        label=metric.title(),
        value=value,
        unit="ft",
        aircraft_label=f"{metric.upper()}1",
        aircraft_type="A320",
        timestamp=1_000.0,
    )


def test_select_record_display_page_keeps_metrics_across_cycles():
    boards = [
        AdsbRecordBoard(
            window="day",
            title="Last 24h",
            observation_count=4,
            records=[
                metric_record("highest", 40_000),
                metric_record("lowest", 1_000),
                metric_record("fastest", 500),
                metric_record("slowest", 120),
                metric_record("furthest", 80),
            ],
        ),
        AdsbRecordBoard(
            window="week",
            title="Last 7d",
            observation_count=1,
            records=[metric_record("nearest", 1)],
        ),
    ]

    assert record_mode_entry_count(boards) == 4

    first_board, first_rows = select_record_display_page(
        boards,
        now=0.0,
        interval_s=10.0,
    )
    second_board, second_rows = select_record_display_page(
        boards,
        now=10.0,
        interval_s=10.0,
    )
    third_board, third_rows = select_record_display_page(
        boards,
        now=20.0,
        interval_s=10.0,
    )
    week_board, week_rows = select_record_display_page(
        boards,
        now=30.0,
        interval_s=10.0,
    )

    assert first_board is boards[0]
    assert [record.metric for record in first_rows] == ["highest", "lowest"]
    assert second_board is boards[0]
    assert [record.metric for record in second_rows] == ["fastest", "slowest"]
    assert third_board is boards[0]
    assert [record.metric for record in third_rows] == ["furthest"]
    assert week_board is boards[1]
    assert [record.metric for record in week_rows] == ["nearest"]
