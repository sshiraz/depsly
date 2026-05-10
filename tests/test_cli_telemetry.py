"""Tests for telemetry CLI commands."""

import json
import os
import sys

from click.testing import CliRunner

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cli import cli
from core.telemetry import load_queued_telemetry_events, telemetry_config_path


class TestTelemetryCli:
    def test_status_defaults_to_disabled(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        result = runner.invoke(cli, ["telemetry", "status"], env=env)

        assert result.exit_code == 0
        assert "Telemetry: disabled" in result.output

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
