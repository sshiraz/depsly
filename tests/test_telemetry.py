"""Tests for local telemetry helpers."""

import json
import os
import sys
from time import perf_counter
from urllib import error as urllib_error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry import (
    DEFAULT_TELEMETRY_URL,
    build_telemetry_event,
    build_telemetry_batch_payload,
    default_telemetry_config,
    delete_local_telemetry_data,
    disable_telemetry,
    duration_bucket,
    enable_telemetry,
    failure_category_for_exception,
    flush_queued_telemetry_events,
    graph_size_bucket,
    load_queued_telemetry_events,
    load_telemetry_config,
    queue_telemetry_event,
    queued_telemetry_event_count,
    sample_telemetry_event,
    should_auto_flush_telemetry,
    telemetry_auto_flush_threshold,
    telemetry_batch_size,
    telemetry_config_path,
    telemetry_endpoint,
    telemetry_enabled,
    telemetry_queue_path,
    telemetry_timeout_seconds,
)


def test_default_telemetry_config_is_disabled():
    config = default_telemetry_config()
    assert config["enabled"] is False
    assert config["install_id"] is None
    assert config["seen_commands"] == []


def test_enable_and_disable_telemetry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))

    enabled = enable_telemetry()
    assert enabled["enabled"] is True
    assert enabled["install_id"]
    assert telemetry_config_path().exists()
    assert telemetry_enabled() is True

    disabled = disable_telemetry()
    assert disabled["enabled"] is False
    assert disabled["install_id"] == enabled["install_id"]
    assert telemetry_enabled() is False


def test_environment_override_forces_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    enable_telemetry()
    monkeypatch.setenv("DEPSLY_TELEMETRY", "0")
    assert telemetry_enabled() is False


def test_duration_bucket_ranges():
    assert duration_bucket(0.1) == "<1s"
    assert duration_bucket(1.0) == "1-5s"
    assert duration_bucket(7.0) == "5-30s"
    assert duration_bucket(45.0) == "30s+"


def test_graph_size_bucket_ranges():
    assert graph_size_bucket(None) == "unknown"
    assert graph_size_bucket(12) == "0-50"
    assert graph_size_bucket(100) == "51-200"
    assert graph_size_bucket(500) == "201-1000"
    assert graph_size_bucket(5000) == "1000+"


def test_queue_and_load_events(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    enable_telemetry()

    event = {
        "event": "cli.command.completed",
        "schema_version": "1",
        "command": "analyze",
        "result": {"success": True, "duration_bucket": "<1s", "graph_size_bucket": "0-50"},
    }
    queue_telemetry_event(event)

    assert telemetry_queue_path().exists()
    assert load_queued_telemetry_events() == [event]


def test_delete_local_telemetry_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    enable_telemetry()
    queue_telemetry_event(sample_telemetry_event())

    assert delete_local_telemetry_data() is True
    assert not telemetry_queue_path().exists()
    assert delete_local_telemetry_data() is False


def test_build_telemetry_event_uses_coarse_fields_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    enable_telemetry()

    started_at = perf_counter()
    event = build_telemetry_event(
        command="recommend",
        started_at=started_at,
        success=True,
        options={
            "include_dev": True,
            "json": False,
            "lockfile": "/tmp/package-lock.json",
            "package_key": "react@19.1.1",
        },
        total_nodes=204,
    )

    assert event["install_id"]
    assert event["command"] == "recommend"
    assert event["options"] == {"include_dev": True, "json": False}
    assert event["result"]["graph_size_bucket"] == "201-1000"
    assert "failure_category" not in event["result"]
    serialized = json.dumps(event)
    assert "/tmp/package-lock.json" not in serialized
    assert "react@19.1.1" not in serialized


def test_build_telemetry_event_marks_first_use(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    enable_telemetry()

    first = build_telemetry_event(
        command="trace",
        started_at=perf_counter(),
        success=True,
        options=None,
        total_nodes=10,
    )
    second = build_telemetry_event(
        command="trace",
        started_at=perf_counter(),
        success=True,
        options=None,
        total_nodes=10,
    )

    assert first["first_use_on_install"] is True
    assert second["first_use_on_install"] is False
    assert "trace" in load_telemetry_config()["seen_commands"]


def test_failure_category_mapping():
    assert failure_category_for_exception(ValueError("Unsupported lockfileVersion: 9")) == "unsupported_lockfile"
    assert failure_category_for_exception(FileNotFoundError("File not found: nope")) == "missing_file"
    assert failure_category_for_exception(ValueError("cannot parse input")) == "parse_error"
    assert failure_category_for_exception(RuntimeError("boom")) == "internal_error"


def test_transport_config_from_environment(monkeypatch):
    monkeypatch.setenv("DEPSLY_TELEMETRY_URL", "https://example.test/v1/telemetry/events")
    monkeypatch.setenv("DEPSLY_TELEMETRY_BATCH_SIZE", "25")
    monkeypatch.setenv("DEPSLY_TELEMETRY_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD", "7")

    assert telemetry_endpoint() == "https://example.test/v1/telemetry/events"
    assert telemetry_batch_size() == 25
    assert telemetry_timeout_seconds() == 1.5
    assert telemetry_auto_flush_threshold() == 7


def test_default_endpoint_is_present(monkeypatch):
    monkeypatch.delenv("DEPSLY_TELEMETRY_URL", raising=False)
    assert telemetry_endpoint() == DEFAULT_TELEMETRY_URL


def test_batch_payload_wraps_events():
    payload = build_telemetry_batch_payload([sample_telemetry_event()])
    assert payload["schema_version"] == "1"
    assert len(payload["events"]) == 1
    assert payload["events"][0]["event"] == "cli.command.completed"


def test_auto_flush_threshold_logic(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    monkeypatch.setenv("DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD", "2")
    enable_telemetry()
    queue_telemetry_event(sample_telemetry_event())

    assert should_auto_flush_telemetry() is False
    queue_telemetry_event(sample_telemetry_event())
    assert should_auto_flush_telemetry() is True


def test_flush_succeeds_and_prunes_sent_events(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    monkeypatch.setenv("DEPSLY_TELEMETRY_URL", "https://example.test/v1/telemetry/events")
    monkeypatch.setenv("DEPSLY_TELEMETRY_BATCH_SIZE", "2")
    enable_telemetry()
    queue_telemetry_event(sample_telemetry_event())
    queue_telemetry_event(sample_telemetry_event())
    queue_telemetry_event(sample_telemetry_event())

    def fake_post(**kwargs):
        assert kwargs["url"] == "https://example.test/v1/telemetry/events"
        assert len(kwargs["payload"]["events"]) == 2
        return {"accepted": 2, "rejected": 0}

    monkeypatch.setattr("core.telemetry._post_telemetry_batch", fake_post)

    result = flush_queued_telemetry_events()

    assert result["attempted"] is True
    assert result["sent"] == 2
    assert result["remaining"] == 1
    assert queued_telemetry_event_count() == 1


def test_flush_failure_keeps_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    monkeypatch.setenv("DEPSLY_TELEMETRY_URL", "https://example.test/v1/telemetry/events")
    enable_telemetry()
    queue_telemetry_event(sample_telemetry_event())

    def fake_post(**kwargs):
        raise urllib_error.URLError("offline")

    monkeypatch.setattr("core.telemetry._post_telemetry_batch", fake_post)

    result = flush_queued_telemetry_events()

    assert result["attempted"] is True
    assert result["sent"] == 0
    assert result["reason"] == "send_failed"
    assert result["remaining"] == 1
    assert queued_telemetry_event_count() == 1
