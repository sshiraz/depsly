"""Tests for telemetry aggregation over raw ingest events."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry import sample_telemetry_event
from core.telemetry_aggregate import (
    build_telemetry_aggregate_report,
    load_raw_telemetry_events,
    summarize_bucket_counts,
    summarize_command_metrics,
    summarize_failure_categories,
    summarize_option_usage,
)
from core.telemetry_ingest import store_telemetry_events


def make_event(*, command: str, success: bool, duration_bucket: str, graph_size_bucket: str, timestamp: str, first_use: bool = False, failure_category: str | None = None, options: dict | None = None) -> dict:
    event = sample_telemetry_event()
    event.update(
        {
            "install_id": "install-123",
            "session_id": "session-123",
            "timestamp": timestamp,
            "depsly_version": "0.1.9",
            "platform": "macos",
            "python_version": "3.11",
            "command": command,
            "first_use_on_install": first_use,
            "options": options or {},
            "result": {
                "success": success,
                "duration_bucket": duration_bucket,
                "graph_size_bucket": graph_size_bucket,
            },
        }
    )
    if failure_category is not None:
        event["result"]["failure_category"] = failure_category
    return event


def test_command_metrics_and_buckets(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    events = [
        make_event(
            command="analyze",
            success=True,
            duration_bucket="<1s",
            graph_size_bucket="0-50",
            timestamp="2026-05-10T20:00:00Z",
            first_use=True,
            options={"json": False},
        ),
        make_event(
            command="analyze",
            success=False,
            duration_bucket="1-5s",
            graph_size_bucket="51-200",
            timestamp="2026-05-10T20:05:00Z",
            failure_category="parse_error",
            options={"json": True},
        ),
        make_event(
            command="recommend",
            success=True,
            duration_bucket="1-5s",
            graph_size_bucket="201-1000",
            timestamp="2026-05-11T20:05:00Z",
            options={"include_dev": True},
        ),
    ]
    store_telemetry_events(db_path, events)

    raw = load_raw_telemetry_events(db_path)
    command_metrics = summarize_command_metrics(raw)
    assert command_metrics[0]["command"] == "analyze"
    assert command_metrics[0]["total_events"] == 2
    assert command_metrics[0]["success_events"] == 1
    assert command_metrics[0]["failure_events"] == 1
    assert command_metrics[0]["first_use_events"] == 1

    duration_rows = summarize_bucket_counts(raw, field="duration_bucket")
    assert any(row["duration_bucket"] == "<1s" and row["event_count"] == 1 for row in duration_rows)
    assert any(
        row["metric_date"] == "2026-05-10"
        and row["command"] == "analyze"
        and row["duration_bucket"] == "1-5s"
        and row["event_count"] == 1
        for row in duration_rows
    )
    assert any(
        row["metric_date"] == "2026-05-11"
        and row["command"] == "recommend"
        and row["duration_bucket"] == "1-5s"
        and row["event_count"] == 1
        for row in duration_rows
    )

    option_rows = summarize_option_usage(raw)
    assert any(row["option_name"] == "json" and row["option_value"] == "true" for row in option_rows)
    assert any(row["option_name"] == "include_dev" and row["option_value"] == "true" for row in option_rows)

    failure_rows = summarize_failure_categories(raw)
    assert failure_rows == [
        {
            "metric_date": "2026-05-10",
            "command": "analyze",
            "depsly_version": "0.1.9",
            "platform": "macos",
            "failure_category": "parse_error",
            "event_count": 1,
        }
    ]


def test_build_aggregate_report(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    store_telemetry_events(
        db_path,
        [
            make_event(
                command="trace",
                success=True,
                duration_bucket="<1s",
                graph_size_bucket="unknown",
                timestamp="2026-05-12T10:00:00Z",
            )
        ],
    )
    report = build_telemetry_aggregate_report(db_path)
    assert report["raw_event_count"] == 1
    assert report["daily_command_metrics"][0]["command"] == "trace"
    assert report["daily_graph_size_buckets"][0]["graph_size_bucket"] == "unknown"
