"""Tests for the telemetry aggregation script entrypoint."""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "telemetry_aggregate.py"


def test_telemetry_aggregate_script_writes_report(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    output_path = tmp_path / "aggregate.json"

    from core.telemetry import sample_telemetry_event
    from core.telemetry_ingest import store_telemetry_events

    event = sample_telemetry_event()
    event.update(
        {
            "install_id": "install-123",
            "session_id": "session-123",
            "timestamp": "2026-05-10T20:00:00Z",
            "depsly_version": "0.1.9",
            "platform": "macos",
            "python_version": "3.11",
            "command": "analyze",
            "options": {"json": False},
        }
    )
    store_telemetry_events(db_path, [event])

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--db-path", str(db_path), "--output", str(output_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )

    assert result.returncode == 0
    assert "Wrote aggregate report:" in result.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["raw_event_count"] == 1
    assert payload["daily_command_metrics"][0]["command"] == "analyze"


def test_telemetry_aggregate_script_supports_text_output(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"

    from core.telemetry import sample_telemetry_event
    from core.telemetry_ingest import store_telemetry_events

    event = sample_telemetry_event()
    event.update(
        {
            "install_id": "install-123",
            "session_id": "session-123",
            "timestamp": "2026-05-10T20:00:00Z",
            "depsly_version": "0.1.9",
            "platform": "macos",
            "python_version": "3.11",
            "command": "trace",
            "options": {"json": False},
        }
    )
    store_telemetry_events(db_path, [event])

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--db-path", str(db_path), "--format", "text"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )

    assert result.returncode == 0
    assert "Depsly Telemetry Summary" in result.stdout
    assert "Raw events: 1" in result.stdout
    assert "- trace: 1 events (100.0%), success 100.0%, first-use 0" in result.stdout
