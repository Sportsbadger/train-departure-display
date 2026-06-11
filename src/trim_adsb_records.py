from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from adsb_records import AdsbRecordTrimResult, trim_adsb_record_store

DEFAULT_STORE_PATH = Path("/data/adsb-records.json")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for ADS-B record trimming."""
    parser = argparse.ArgumentParser(
        description="Trim erroneous entries from the ADS-B records store.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE_PATH,
        help=f"ADS-B records JSON path. Default: {DEFAULT_STORE_PATH}",
    )
    parser.add_argument(
        "--hex",
        dest="hex_values",
        action="append",
        default=[],
        help="Aircraft hex identifier to remove from rolling observations.",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help=(
            "Aircraft label/callsign to remove from observations and "
            "all-time records."
        ),
    )
    parser.add_argument(
        "--forever-metric",
        action="append",
        default=[],
        choices=(
            "highest",
            "lowest",
            "fastest",
            "slowest",
            "furthest",
            "nearest",
            "climb",
            "descent",
        ),
        help=(
            "All-time metric to clear when the bad all-time row is "
            "already saved."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without writing the store.",
    )
    return parser.parse_args(argv)


def format_result(result: AdsbRecordTrimResult, *, dry_run: bool) -> str:
    """Format a trim result for terminal output."""
    prefix = "Would trim" if dry_run else "Trimmed"
    observations_removed = result.observations_before - result.observations_after
    forever_removed = result.forever_before - result.forever_after
    return (
        f"{prefix} {observations_removed} observations "
        f"({result.observations_before} -> {result.observations_after}) and "
        f"{forever_removed} all-time records "
        f"({result.forever_before} -> {result.forever_after})."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ADS-B record trim command."""
    args = parse_args(argv)
    result = trim_adsb_record_store(
        args.store,
        hex_values=args.hex_values,
        labels=args.label,
        forever_metrics=args.forever_metric,
        dry_run=args.dry_run,
    )
    print(format_result(result, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
