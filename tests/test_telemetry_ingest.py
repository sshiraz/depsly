"""Tests for telemetry ingestion validation and persistence."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry import sample_telemetry_event
from core.telemetry_ingest import (
    count_stored_telemetry_events,
    init_telemetry_ingest_db,
    store_telemetry_events,
    validate_telemetry_batch,
    validate_telemetry_event,
)


def valid_event() -> dict:
    event = sample_telemetry_event()
    event.update(
        {
            "install_id": "install-123",
            "session_id": "session-123",
            "timestamp": "2026-05-10T20:00:00Z",
            "depsly_version": "0.1.9",
            "platform": "macos",
            "python_version": "3.11",
            "options": {"json": False},
        }
    )
    return event


def valid_batch() -> dict:
    return {
        "schema_version": "1",
        "sent_at": "2026-05-10T20:00:01Z",
        "events": [valid_event()],
    }


def test_validate_telemetry_event_accepts_valid_shape():
    assert validate_telemetry_event(valid_event()) == []


def test_validate_telemetry_event_rejects_extra_fields():
    event = valid_event()
    event["project_name"] = "secret"
    errors = validate_telemetry_event(event)
    assert "events[0].project_name is not allowed" in errors


def test_validate_telemetry_batch_accepts_valid_payload():
    result = validate_telemetry_batch(valid_batch())
    assert result.ok is True
    assert result.accepted == 1
    assert result.rejected == 0


def test_validate_telemetry_batch_rejects_invalid_payload():
    payload = valid_batch()
    payload["events"][0]["command"] = "rm -rf"
    result = validate_telemetry_batch(payload)
    assert result.ok is False
    assert result.accepted == 0
    assert result.rejected == 1
    assert any("command is invalid" in error for error in result.errors)


def test_init_db_and_store_events(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    init_telemetry_ingest_db(db_path)
    assert db_path.exists()

    stored = store_telemetry_events(db_path, [valid_event(), valid_event()])
    assert stored == 2
    assert count_stored_telemetry_events(db_path) == 2
