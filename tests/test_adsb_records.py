from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from adsb import AdsbAircraft  # noqa: E402
from adsb_records import (  # noqa: E402
    AdsbRecordBoard,
    AdsbMetricRecord,
    build_record_summary_text,
    filter_record_boards,
    load_adsb_record_boards,
    normalize_record_windows,
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


def test_update_adsb_record_store_builds_rolling_and_all_time_records(tmp_path):
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
    assert day.title == "Last 24 Hours"
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
    all_time = reloaded[2]
    assert all_time.window == "forever"
    assert all_time.title == "All Time"
    assert all_time.records[0].aircraft_label == "OLDER"
    assert all_time.records[4].aircraft_label == "OLDER"


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


def test_select_record_display_page_keeps_full_window_cycle_together():
    boards = [
        AdsbRecordBoard(
            window="day",
            title="Last 24 Hours",
            observation_count=4,
            records=[
                metric_record("highest", 40_000),
                metric_record("lowest", 1_000),
                metric_record("fastest", 500),
                metric_record("slowest", 120),
                metric_record("furthest", 80),
                metric_record("nearest", 1),
                metric_record("climb", 2_000),
                metric_record("descent", -1_500),
            ],
        ),
        AdsbRecordBoard(
            window="week",
            title="Last 7 Days",
            observation_count=1,
            records=[metric_record("highest", 41_000)],
        ),
    ]

    assert record_mode_entry_count(boards) == 5

    expected_day_pages = [
        (0.0, ["highest", "lowest"]),
        (10.0, ["fastest", "slowest"]),
        (20.0, ["furthest", "nearest"]),
        (30.0, ["climb", "descent"]),
    ]
    for now, expected_metrics in expected_day_pages:
        board, rows = select_record_display_page(
            boards,
            now=now,
            interval_s=10.0,
        )
        assert board is boards[0]
        assert [record.metric for record in rows] == expected_metrics

    week_board, week_rows = select_record_display_page(
        boards,
        now=40.0,
        interval_s=10.0,
    )

    assert week_board is boards[1]
    assert [record.metric for record in week_rows] == ["highest"]


def test_normalize_record_windows_accepts_requested_totals():
    assert normalize_record_windows("24hr,7 day,All Time") == [
        "day",
        "week",
        "forever",
    ]
    assert normalize_record_windows("all-time,24 hours,all") == [
        "forever",
        "day",
    ]
    assert normalize_record_windows("unknown") == ["day", "week", "forever"]


def test_filter_record_boards_uses_configured_windows():
    boards = [
        AdsbRecordBoard("day", "Last 24 Hours", 0, []),
        AdsbRecordBoard("week", "Last 7 Days", 0, []),
        AdsbRecordBoard("forever", "All Time", 0, []),
    ]

    filtered = filter_record_boards(boards, ["day", "forever"])

    assert [board.window for board in filtered] == ["day", "forever"]
