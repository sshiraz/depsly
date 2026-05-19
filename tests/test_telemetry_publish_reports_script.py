"""Tests for the scheduled telemetry report publishing script."""

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "telemetry_publish_reports.py"


def test_telemetry_publish_reports_script_writes_artifacts(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    output_dir = tmp_path / "reports"

    from core.telemetry import sample_telemetry_event
    from core.telemetry_ingest import store_telemetry_events

    event = sample_telemetry_event()
    event.update(
        {
            "install_id": "install-123",
            "session_id": "session-123",
            "timestamp": "2026-05-10T20:00:00Z",
            "depsly_version": "0.1.10",
            "platform": "macos",
            "python_version": "3.11",
            "command": "analyze",
            "options": {"json": False},
        }
    )
    store_telemetry_events(db_path, [event])

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db-path",
            str(db_path),
            "--output-dir",
            str(output_dir),
            "--report-date",
            "2026-05-10",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )

    assert result.returncode == 0
    assert "Wrote dated JSON report:" in result.stdout
    assert "Updated latest text report:" in result.stdout

    dated_json = output_dir / "2026-05-10-telemetry-report.json"
    dated_text = output_dir / "2026-05-10-telemetry-report.txt"
    latest_json = output_dir / "latest-telemetry-report.json"
    latest_text = output_dir / "latest-telemetry-report.txt"

    payload = json.loads(dated_json.read_text(encoding="utf-8"))
    assert payload["raw_event_count"] == 1
    assert payload["daily_command_metrics"][0]["command"] == "analyze"
    assert "Depsly Telemetry Summary" in dated_text.read_text(encoding="utf-8")
    assert latest_json.read_text(encoding="utf-8") == dated_json.read_text(encoding="utf-8")
    assert latest_text.read_text(encoding="utf-8") == dated_text.read_text(encoding="utf-8")
