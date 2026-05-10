"""Telemetry aggregation over the raw ingest SQLite store."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path


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
