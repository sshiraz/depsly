"""Write scheduled telemetry aggregate artifacts for operator review."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.telemetry_aggregate import write_telemetry_report_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write date-stamped and latest telemetry aggregate reports."
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
        help="Directory to receive dated and latest report artifacts.",
    )
    parser.add_argument(
        "--report-date",
        type=date.fromisoformat,
        help="Optional YYYY-MM-DD date to use in dated artifact filenames.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = write_telemetry_report_bundle(
        args.db_path,
        args.output_dir,
        report_date=args.report_date,
    )
    print(f"Wrote dated JSON report: {written['dated_json']}")
    print(f"Wrote dated text report: {written['dated_text']}")
    print(f"Updated latest JSON report: {written['latest_json']}")
    print(f"Updated latest text report: {written['latest_text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
