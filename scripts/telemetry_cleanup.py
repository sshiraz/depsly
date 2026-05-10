"""Prune old telemetry raw events and dated report artifacts."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.telemetry_aggregate import cleanup_telemetry_report_artifacts
from core.telemetry_ingest import prune_stored_telemetry_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply retention cleanup to telemetry raw events and report artifacts."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=ROOT / "var" / "telemetry" / "telemetry.sqlite3",
        help="SQLite path for raw telemetry events.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "var" / "telemetry" / "reports",
        help="Directory containing dated telemetry report artifacts.",
    )
    parser.add_argument(
        "--raw-retain-days",
        type=int,
        default=30,
        help="Retention window in days for raw telemetry events (default: 30).",
    )
    parser.add_argument(
        "--report-retain-days",
        type=int,
        default=90,
        help="Retention window in days for dated report artifacts (default: 90).",
    )
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        help="Optional YYYY-MM-DD date to use as the retention cutoff reference.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reference_now = None
    if args.reference_date is not None:
        reference_now = datetime.combine(args.reference_date, datetime.min.time(), tzinfo=UTC)
    deleted_raw = prune_stored_telemetry_events(
        args.db_path,
        retain_days=args.raw_retain_days,
        now=reference_now,
    )
    deleted_reports = cleanup_telemetry_report_artifacts(
        args.output_dir,
        retain_days=args.report_retain_days,
        reference_date=args.reference_date,
    )
    print(f"Deleted raw telemetry events: {deleted_raw}")
    print(f"Deleted dated report artifacts: {len(deleted_reports)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
