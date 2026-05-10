"""Tests for telemetry ingest request handling."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.telemetry import sample_telemetry_event
from core.telemetry_ingest import count_stored_telemetry_events, handle_ingest_post, health_response
from scripts import telemetry_ingest_server


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


def valid_batch_bytes() -> bytes:
    import json

    return json.dumps(
        {
            "schema_version": "1",
            "sent_at": "2026-05-10T20:00:01Z",
            "events": [valid_event()],
        }
    ).encode("utf-8")


def test_health_response_reports_ok(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    status, payload = health_response(db_path)
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["stored_events"] == 0


def test_post_valid_batch_is_accepted_and_stored(tmp_path):
    db_path = tmp_path / "telemetry.sqlite3"
    body = valid_batch_bytes()
    status, payload = handle_ingest_post(
        path="/v1/telemetry/events",
        content_length_header=str(len(body)),
        raw_body=body,
        db_path=db_path,
    )
    assert status == 202
    assert payload == {"accepted": 1, "rejected": 0}
    assert count_stored_telemetry_events(db_path) == 1


def test_post_invalid_batch_returns_400(tmp_path):
    import json

    db_path = tmp_path / "telemetry.sqlite3"
    payload = {
        "schema_version": "1",
        "sent_at": "2026-05-10T20:00:01Z",
        "events": [valid_event() | {"platform": "beos"}],
    }
    body = json.dumps(payload).encode("utf-8")
    status, response = handle_ingest_post(
        path="/v1/telemetry/events",
        content_length_header=str(len(body)),
        raw_body=body,
        db_path=db_path,
    )
    assert status == 400
    assert response["accepted"] == 0
    assert response["rejected"] == 1
    assert any("platform is invalid" in error for error in response["errors"])


def test_post_unknown_path_returns_404(tmp_path):
    body = valid_batch_bytes()
    status, payload = handle_ingest_post(
        path="/wrong",
        content_length_header=str(len(body)),
        raw_body=body,
        db_path=tmp_path / "telemetry.sqlite3",
    )
    assert status == 404
    assert payload == {"error": "not_found"}


def test_parse_args_reads_environment_defaults(monkeypatch):
    monkeypatch.setenv("DEPSLY_TELEMETRY_INGEST_HOST", "0.0.0.0")
    monkeypatch.setenv("DEPSLY_TELEMETRY_INGEST_PORT", "9797")
    monkeypatch.setenv("DEPSLY_TELEMETRY_INGEST_DB_PATH", "/tmp/depsly-telemetry.sqlite3")
    monkeypatch.setattr(sys, "argv", ["telemetry_ingest_server.py"])

    args = telemetry_ingest_server.parse_args()

    assert args.host == "0.0.0.0"
    assert args.port == 9797
    assert args.db_path == Path("/tmp/depsly-telemetry.sqlite3")
