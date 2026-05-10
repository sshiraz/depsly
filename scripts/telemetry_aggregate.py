"""Aggregate stored telemetry events into daily JSON summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.telemetry_aggregate import build_telemetry_aggregate_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate raw Depsly telemetry events.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=ROOT / "var" / "telemetry" / "telemetry.sqlite3",
        help="SQLite path for raw telemetry events.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path. Prints to stdout when omitted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_telemetry_aggregate_report(args.db_path)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote aggregate report: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
