"""Tests for the telemetry cleanup script."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "telemetry_cleanup.py"


def test_telemetry_cleanup_script_prunes_raw_events_and_reports(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()

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
    store_telemetry_events(db_path, [event, event])

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "update telemetry_raw_events set received_at = ? where id = 1",
            ("2026-03-01T00:00:00Z",),
        )
        conn.execute(
            "update telemetry_raw_events set received_at = ? where id = 2",
            ("2099-05-09T00:00:00Z",),
        )
        conn.commit()

    (output_dir / "2026-01-01-telemetry-report.json").write_text("old", encoding="utf-8")
    (output_dir / "2026-01-01-telemetry-report.txt").write_text("old", encoding="utf-8")
    (output_dir / "latest-telemetry-report.json").write_text("latest", encoding="utf-8")
    (output_dir / "latest-telemetry-report.txt").write_text("latest", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db-path",
            str(db_path),
            "--output-dir",
            str(output_dir),
            "--raw-retain-days",
            "30",
            "--report-retain-days",
            "90",
            "--reference-date",
            "2026-05-10",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )

    assert result.returncode == 0
    assert "Deleted raw telemetry events:" in result.stdout
    assert "Deleted dated report artifacts:" in result.stdout
    assert not (output_dir / "2026-01-01-telemetry-report.json").exists()
    assert not (output_dir / "2026-01-01-telemetry-report.txt").exists()
    assert (output_dir / "latest-telemetry-report.json").exists()
    assert (output_dir / "latest-telemetry-report.txt").exists()

    with sqlite3.connect(db_path) as conn:
        remaining = conn.execute("select count(*) from telemetry_raw_events").fetchone()[0]
    assert remaining == 1
