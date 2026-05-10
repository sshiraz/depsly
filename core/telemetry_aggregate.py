"""Telemetry aggregation over the raw ingest SQLite store."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


DURATION_BUCKET_ORDER = ["<1s", "1-5s", "5-30s", "30s+"]
GRAPH_SIZE_BUCKET_ORDER = ["unknown", "0-50", "51-200", "201-1000", "1000+"]
DATED_REPORT_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-telemetry-report\.(json|txt)$")


def load_raw_telemetry_events(db_path: Path) -> list[dict]:
    """Load stored raw telemetry events from the SQLite ingest database."""
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            select event_json
            from telemetry_raw_events
            order by event_timestamp asc, id asc
            """
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def _metric_date(timestamp: str) -> str:
    """Extract YYYY-MM-DD from an ISO-8601 event timestamp."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()


def summarize_command_metrics(events: list[dict]) -> list[dict]:
    """Aggregate daily command-level usage metrics."""
    grouped: dict[tuple[str, str, str, str], dict] = {}
    for event in events:
        key = (
            _metric_date(event["timestamp"]),
            event["command"],
            event["depsly_version"],
            event["platform"],
        )
        if key not in grouped:
            grouped[key] = {
                "metric_date": key[0],
                "command": key[1],
                "depsly_version": key[2],
                "platform": key[3],
                "total_events": 0,
                "success_events": 0,
                "failure_events": 0,
                "first_use_events": 0,
            }
        row = grouped[key]
        row["total_events"] += 1
        row["success_events"] += 1 if event["result"]["success"] else 0
        row["failure_events"] += 0 if event["result"]["success"] else 1
        row["first_use_events"] += 1 if event.get("first_use_on_install") else 0
    return [grouped[key] for key in sorted(grouped)]


def summarize_bucket_counts(events: list[dict], *, field: str) -> list[dict]:
    """Aggregate daily bucket counts for one result field."""
    grouped: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    for event in events:
        bucket = event["result"][field]
        key = (
            _metric_date(event["timestamp"]),
            event["command"],
            event["depsly_version"],
            event["platform"],
            bucket,
        )
        grouped[key] += 1

    row_field = "duration_bucket" if field == "duration_bucket" else "graph_size_bucket"
    return [
        {
            "metric_date": key[0],
            "command": key[1],
            "depsly_version": key[2],
            "platform": key[3],
            row_field: key[4],
            "event_count": grouped[key],
        }
        for key in sorted(grouped)
    ]


def summarize_option_usage(events: list[dict]) -> list[dict]:
    """Aggregate daily option usage counts."""
    grouped: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
    for event in events:
        for option_name, option_value in sorted(event.get("options", {}).items()):
            key = (
                _metric_date(event["timestamp"]),
                event["command"],
                event["depsly_version"],
                event["platform"],
                option_name,
                str(option_value).lower(),
            )
            grouped[key] += 1

    return [
        {
            "metric_date": key[0],
            "command": key[1],
            "depsly_version": key[2],
            "platform": key[3],
            "option_name": key[4],
            "option_value": key[5],
            "event_count": grouped[key],
        }
        for key in sorted(grouped)
    ]


def summarize_failure_categories(events: list[dict]) -> list[dict]:
    """Aggregate daily failure category counts."""
    grouped: dict[tuple[str, str, str, str, str], int] = defaultdict(int)
    for event in events:
        failure_category = event["result"].get("failure_category")
        if not failure_category:
            continue
        key = (
            _metric_date(event["timestamp"]),
            event["command"],
            event["depsly_version"],
            event["platform"],
            failure_category,
        )
        grouped[key] += 1

    return [
        {
            "metric_date": key[0],
            "command": key[1],
            "depsly_version": key[2],
            "platform": key[3],
            "failure_category": key[4],
            "event_count": grouped[key],
        }
        for key in sorted(grouped)
    ]


def build_telemetry_aggregate_report(db_path: Path) -> dict:
    """Build a deterministic aggregate telemetry report from the raw ingest DB."""
    events = load_raw_telemetry_events(db_path)
    return {
        "raw_event_count": len(events),
        "daily_command_metrics": summarize_command_metrics(events),
        "daily_duration_buckets": summarize_bucket_counts(events, field="duration_bucket"),
        "daily_graph_size_buckets": summarize_bucket_counts(events, field="graph_size_bucket"),
        "daily_option_usage": summarize_option_usage(events),
        "daily_failure_categories": summarize_failure_categories(events),
    }


def _bucket_sort_key(bucket: str, ordered_buckets: list[str]) -> tuple[int, str]:
    if bucket in ordered_buckets:
        return (ordered_buckets.index(bucket), bucket)
    return (len(ordered_buckets), bucket)


def render_telemetry_text_report(report: dict) -> str:
    """Render a concise human-readable telemetry report."""
    if report["raw_event_count"] == 0:
        return "Depsly Telemetry Summary\n\nNo telemetry events found.\n"

    command_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total_events": 0,
            "success_events": 0,
            "failure_events": 0,
            "first_use_events": 0,
        }
    )
    metric_dates: set[str] = set()
    for row in report["daily_command_metrics"]:
        metric_dates.add(row["metric_date"])
        totals = command_totals[row["command"]]
        totals["total_events"] += row["total_events"]
        totals["success_events"] += row["success_events"]
        totals["failure_events"] += row["failure_events"]
        totals["first_use_events"] += row["first_use_events"]

    duration_totals: dict[str, int] = defaultdict(int)
    for row in report["daily_duration_buckets"]:
        duration_totals[row["duration_bucket"]] += row["event_count"]

    graph_size_totals: dict[str, int] = defaultdict(int)
    for row in report["daily_graph_size_buckets"]:
        graph_size_totals[row["graph_size_bucket"]] += row["event_count"]

    failure_totals: dict[str, int] = defaultdict(int)
    for row in report["daily_failure_categories"]:
        failure_totals[row["failure_category"]] += row["event_count"]

    option_totals: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in report["daily_option_usage"]:
        option_key = (row["command"], row["option_name"], row["option_value"])
        option_totals[option_key] += row["event_count"]

    total_events = report["raw_event_count"]
    sorted_dates = sorted(metric_dates)
    lines = [
        "Depsly Telemetry Summary",
        "",
        f"Raw events: {total_events}",
        f"Date range: {sorted_dates[0]} to {sorted_dates[-1]}",
        "",
        "Command usage:",
    ]

    sorted_commands = sorted(
        command_totals.items(),
        key=lambda item: (-item[1]["total_events"], item[0]),
    )
    for command, totals in sorted_commands:
        share = (totals["total_events"] / total_events) * 100
        success_rate = (totals["success_events"] / totals["total_events"]) * 100
        lines.append(
            f"- {command}: {totals['total_events']} events ({share:.1f}%), "
            f"success {success_rate:.1f}%, first-use {totals['first_use_events']}"
        )

    lines.extend(["", "Duration buckets:"])
    for bucket, count in sorted(
        duration_totals.items(),
        key=lambda item: _bucket_sort_key(item[0], DURATION_BUCKET_ORDER),
    ):
        lines.append(f"- {bucket}: {count}")

    lines.extend(["", "Graph size buckets:"])
    for bucket, count in sorted(
        graph_size_totals.items(),
        key=lambda item: _bucket_sort_key(item[0], GRAPH_SIZE_BUCKET_ORDER),
    ):
        lines.append(f"- {bucket}: {count}")

    if failure_totals:
        lines.extend(["", "Failure categories:"])
        for category, count in sorted(failure_totals.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {category}: {count}")

    if option_totals:
        lines.extend(["", "Top option usage:"])
        for (command, option_name, option_value), count in sorted(
            option_totals.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
        )[:10]:
            lines.append(f"- {command}: {option_name}={option_value} ({count})")

    return "\n".join(lines) + "\n"


def write_telemetry_report_bundle(
    db_path: Path,
    output_dir: Path,
    *,
    report_date: date | None = None,
) -> dict[str, Path]:
    """Write date-stamped JSON/text aggregate reports plus stable latest copies."""
    effective_date = report_date or datetime.now(UTC).date()
    report = build_telemetry_aggregate_report(db_path)
    json_rendered = json.dumps(report, indent=2) + "\n"
    text_rendered = render_telemetry_text_report(report)

    output_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = effective_date.isoformat()
    dated_json_path = output_dir / f"{date_prefix}-telemetry-report.json"
    dated_text_path = output_dir / f"{date_prefix}-telemetry-report.txt"
    latest_json_path = output_dir / "latest-telemetry-report.json"
    latest_text_path = output_dir / "latest-telemetry-report.txt"

    dated_json_path.write_text(json_rendered, encoding="utf-8")
    dated_text_path.write_text(text_rendered, encoding="utf-8")
    latest_json_path.write_text(json_rendered, encoding="utf-8")
    latest_text_path.write_text(text_rendered, encoding="utf-8")

    return {
        "dated_json": dated_json_path,
        "dated_text": dated_text_path,
        "latest_json": latest_json_path,
        "latest_text": latest_text_path,
    }


def cleanup_telemetry_report_artifacts(
    output_dir: Path,
    *,
    retain_days: int,
    reference_date: date | None = None,
) -> list[Path]:
    """Delete dated telemetry report artifacts older than the retention window."""
    if retain_days < 0:
        raise ValueError("retain_days must be non-negative")
    if not output_dir.exists():
        return []

    effective_date = reference_date or datetime.now(UTC).date()
    cutoff_date = effective_date - timedelta(days=retain_days)
    deleted: list[Path] = []

    for path in sorted(output_dir.iterdir()):
        match = DATED_REPORT_PATTERN.match(path.name)
        if not match:
            continue
        report_date = date.fromisoformat(match.group(1))
        if report_date < cutoff_date:
            path.unlink()
            deleted.append(path)

    return deleted
