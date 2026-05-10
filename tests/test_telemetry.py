"""Tests for local telemetry helpers."""

import json
import os
import sys
from time import perf_counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.telemetry import (
    build_telemetry_event,
    default_telemetry_config,
    delete_local_telemetry_data,
    disable_telemetry,
    duration_bucket,
    enable_telemetry,
    failure_category_for_exception,
    graph_size_bucket,
    load_queued_telemetry_events,
    load_telemetry_config,
    queue_telemetry_event,
    sample_telemetry_event,
    telemetry_config_path,
    telemetry_enabled,
    telemetry_queue_path,
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
