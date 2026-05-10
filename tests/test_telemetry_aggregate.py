"""Tests for telemetry aggregation over raw ingest events."""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry import sample_telemetry_event
from core.telemetry_aggregate import (
    build_telemetry_aggregate_report,
    cleanup_telemetry_report_artifacts,
    load_raw_telemetry_events,
    render_telemetry_text_report,
    summarize_bucket_counts,
    summarize_command_metrics,
    summarize_failure_categories,
    summarize_option_usage,
    write_telemetry_report_bundle,
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


def test_render_text_report(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    store_telemetry_events(
        db_path,
        [
            make_event(
                command="analyze",
                success=True,
                duration_bucket="<1s",
                graph_size_bucket="0-50",
                timestamp="2026-05-10T10:00:00Z",
                first_use=True,
                options={"json": True},
            ),
            make_event(
                command="analyze",
                success=False,
                duration_bucket="1-5s",
                graph_size_bucket="51-200",
                timestamp="2026-05-10T10:01:00Z",
                failure_category="parse_error",
                options={"json": True},
            ),
            make_event(
                command="trace",
                success=True,
                duration_bucket="5-30s",
                graph_size_bucket="201-1000",
                timestamp="2026-05-11T10:02:00Z",
                options={"json": False},
            ),
        ],
    )
    report = build_telemetry_aggregate_report(db_path)
    rendered = render_telemetry_text_report(report)

    assert "Depsly Telemetry Summary" in rendered
    assert "Raw events: 3" in rendered
    assert "Date range: 2026-05-10 to 2026-05-11" in rendered
    assert "- analyze: 2 events (66.7%), success 50.0%, first-use 1" in rendered
    assert "- trace: 1 events (33.3%), success 100.0%, first-use 0" in rendered
    assert "Failure categories:" in rendered
    assert "- parse_error: 1" in rendered
    assert "Top option usage:" in rendered
    assert "- analyze: json=true (2)" in rendered


def test_render_text_report_for_empty_db(tmp_path):
    report = build_telemetry_aggregate_report(tmp_path / "missing.sqlite3")
    rendered = render_telemetry_text_report(report)
    assert rendered == "Depsly Telemetry Summary\n\nNo telemetry events found.\n"


def test_write_telemetry_report_bundle(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    output_dir = tmp_path / "reports"
    store_telemetry_events(
        db_path,
        [
            make_event(
                command="analyze",
                success=True,
                duration_bucket="<1s",
                graph_size_bucket="0-50",
                timestamp="2026-05-10T10:00:00Z",
            )
        ],
    )

    written = write_telemetry_report_bundle(
        db_path,
        output_dir,
        report_date=date(2026, 5, 10),
    )

    assert written["dated_json"] == output_dir / "2026-05-10-telemetry-report.json"
    assert written["dated_text"] == output_dir / "2026-05-10-telemetry-report.txt"
    assert written["latest_json"] == output_dir / "latest-telemetry-report.json"
    assert written["latest_text"] == output_dir / "latest-telemetry-report.txt"
    assert '"raw_event_count": 1' in written["dated_json"].read_text(encoding="utf-8")
    assert "Depsly Telemetry Summary" in written["dated_text"].read_text(encoding="utf-8")
    assert written["latest_json"].read_text(encoding="utf-8") == written["dated_json"].read_text(
        encoding="utf-8"
    )
    assert written["latest_text"].read_text(encoding="utf-8") == written["dated_text"].read_text(
        encoding="utf-8"
    )


def test_cleanup_telemetry_report_artifacts(tmp_path):
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    old_json = output_dir / "2026-01-01-telemetry-report.json"
    old_txt = output_dir / "2026-01-01-telemetry-report.txt"
    keep_json = output_dir / "2026-05-01-telemetry-report.json"
    keep_txt = output_dir / "2026-05-01-telemetry-report.txt"
    latest_json = output_dir / "latest-telemetry-report.json"
    latest_txt = output_dir / "latest-telemetry-report.txt"
    for path in [old_json, old_txt, keep_json, keep_txt, latest_json, latest_txt]:
        path.write_text("stub", encoding="utf-8")

    deleted = cleanup_telemetry_report_artifacts(
        output_dir,
        retain_days=30,
        reference_date=date(2026, 5, 10),
    )

    assert deleted == [old_json, old_txt]
    assert not old_json.exists()
    assert not old_txt.exists()
    assert keep_json.exists()
    assert keep_txt.exists()
    assert latest_json.exists()
    assert latest_txt.exists()
