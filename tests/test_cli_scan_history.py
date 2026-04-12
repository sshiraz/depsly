"""Tests for list-scans and compare-scans CLI commands."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli


LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")


class TestScanHistoryCli:
    def test_list_scans_shows_saved_scan(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        save_result = runner.invoke(cli, ["save-scan", LOCKFILE, "--limit", "1"], env=env)
        assert save_result.exit_code == 0

        result = runner.invoke(cli, ["list-scans"], env=env)
        assert result.exit_code == 0
        assert "frontend" in result.output
        assert ".json" in result.output

    def test_list_scans_can_filter_by_project(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        runner.invoke(cli, ["save-scan", LOCKFILE, "--limit", "1"], env=env)
        result = runner.invoke(cli, ["list-scans", "--project", "frontend"], env=env)

        assert result.exit_code == 0
        assert "frontend" in result.output

    def test_compare_scans_outputs_human_summary(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        first = runner.invoke(cli, ["save-scan", LOCKFILE, "--limit", "1"], env=env)
        second = runner.invoke(cli, ["save-scan", LOCKFILE, "--no-dev", "--limit", "1"], env=env)
        first_path = first.output.strip().split("Saved scan: ", 1)[1]
        second_path = second.output.strip().split("Saved scan: ", 1)[1]

        result = runner.invoke(cli, ["compare-scans", first_path, second_path], env=env)

        assert result.exit_code == 0
        assert result.output.startswith("Scan Comparison")
        assert "Dependency changes:" in result.output
        assert "Top recommendation:" in result.output

    def test_compare_scans_outputs_json(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        first = runner.invoke(cli, ["save-scan", LOCKFILE, "--limit", "1"], env=env)
        second = runner.invoke(cli, ["save-scan", LOCKFILE, "--no-dev", "--limit", "1"], env=env)
        first_path = first.output.strip().split("Saved scan: ", 1)[1]
        second_path = second.output.strip().split("Saved scan: ", 1)[1]

        result = runner.invoke(cli, ["compare-scans", first_path, second_path, "--json"], env=env)

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert list(parsed.keys()) == ["project", "scan", "dependencies", "recommendations"]
