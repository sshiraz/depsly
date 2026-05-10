"""Tests for telemetry CLI commands."""

import json
import os
import sys

from click.testing import CliRunner

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cli import cli
from core.telemetry import DEFAULT_TELEMETRY_URL, load_queued_telemetry_events, telemetry_config_path


class TestTelemetryCli:
    def test_status_defaults_to_disabled(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        result = runner.invoke(cli, ["telemetry", "status"], env=env)

        assert result.exit_code == 0
        assert "Telemetry: disabled" in result.output
        assert "Queued local events: 0" in result.output
        assert f"Upload endpoint: {DEFAULT_TELEMETRY_URL}" in result.output

    def test_enable_and_disable(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])

        enabled = runner.invoke(cli, ["telemetry", "enable"], env=env)
        assert enabled.exit_code == 0
        assert "Telemetry enabled." in enabled.output
        assert telemetry_config_path().exists()

        status = runner.invoke(cli, ["telemetry", "status"], env=env)
        assert status.exit_code == 0
        assert "Telemetry: enabled" in status.output
        assert "Queued local events: 0" in status.output
        assert f"Upload endpoint: {DEFAULT_TELEMETRY_URL}" in status.output

        disabled = runner.invoke(cli, ["telemetry", "disable"], env=env)
        assert disabled.exit_code == 0
        assert "Telemetry disabled." in disabled.output

    def test_show_sample_outputs_json(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        result = runner.invoke(cli, ["telemetry", "show-sample"], env=env)

        assert result.exit_code == 0
        assert "Sample telemetry event:" in result.output
        payload = json.loads(result.output.split("\n", 2)[2])
        assert payload["event"] == "cli.command.completed"
        assert payload["command"] == "recommend"

    def test_delete_data_removes_queue(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])

        runner.invoke(cli, ["telemetry", "enable"], env=env)
        runner.invoke(cli, ["analyze", "frontend/package-lock.json"], env=env)
        assert load_queued_telemetry_events()

        result = runner.invoke(cli, ["telemetry", "delete-data"], env=env)

        assert result.exit_code == 0
        assert "Local telemetry data deleted." in result.output
        assert load_queued_telemetry_events() == []

    def test_flush_runs_with_default_endpoint(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])
        monkeypatch.setenv("DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD", "100")

        runner.invoke(cli, ["telemetry", "enable"], env=env)
        runner.invoke(cli, ["analyze", "frontend/package-lock.json"], env=env)

        def fake_flush():
            return {"attempted": True, "sent": 1, "remaining": 0, "reason": "sent"}

        monkeypatch.setattr("cli.flush_queued_telemetry_events", fake_flush)

        result = runner.invoke(cli, ["telemetry", "flush"], env=env)

        assert result.exit_code == 0
        assert "Telemetry flush complete." in result.output
        assert "Events sent: 1" in result.output

    def test_flush_reports_success(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {
            "DEPSLY_HOME": str(tmp_path / "depsly-home"),
            "DEPSLY_TELEMETRY_URL": "https://example.test/v1/telemetry/events",
        }
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])

        runner.invoke(cli, ["telemetry", "enable"], env=env)
        runner.invoke(cli, ["analyze", "frontend/package-lock.json"], env=env)

        def fake_flush():
            return {"attempted": True, "sent": 1, "remaining": 0, "reason": "sent"}

        monkeypatch.setattr("cli.flush_queued_telemetry_events", fake_flush)

        result = runner.invoke(cli, ["telemetry", "flush"], env=env)

        assert result.exit_code == 0
        assert "Telemetry flush complete." in result.output
        assert "Events sent: 1" in result.output

    def test_flush_reports_failure(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {
            "DEPSLY_HOME": str(tmp_path / "depsly-home"),
            "DEPSLY_TELEMETRY_URL": "https://example.test/v1/telemetry/events",
        }
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])

        def fake_flush():
            return {"attempted": True, "sent": 0, "remaining": 3, "reason": "send_failed"}

        monkeypatch.setattr("cli.flush_queued_telemetry_events", fake_flush)

        result = runner.invoke(cli, ["telemetry", "flush"], env=env)

        assert result.exit_code == 0
        assert "Telemetry flush failed." in result.output
        assert "Queued local events remain: 3" in result.output

    def test_auto_flush_triggers_only_after_threshold(self, tmp_path, monkeypatch):
        runner = CliRunner()
        env = {
            "DEPSLY_HOME": str(tmp_path / "depsly-home"),
            "DEPSLY_TELEMETRY_AUTO_FLUSH_THRESHOLD": "2",
        }
        monkeypatch.setenv("DEPSLY_HOME", env["DEPSLY_HOME"])
        
        def fake_post(**kwargs):
            return {"accepted": len(kwargs["payload"]["events"]), "rejected": 0}

        monkeypatch.setattr("core.telemetry._post_telemetry_batch", fake_post)

        runner.invoke(cli, ["telemetry", "enable"], env=env)
        runner.invoke(cli, ["analyze", "frontend/package-lock.json"], env=env)
        assert len(load_queued_telemetry_events()) == 1
        runner.invoke(cli, ["analyze", "frontend/package-lock.json"], env=env)
        assert load_queued_telemetry_events() == []
