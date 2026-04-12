"""Tests for the save-scan CLI command."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli


LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")


class TestSaveScanCli:
    def test_save_scan_persists_normalized_export(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        result = runner.invoke(cli, ["save-scan", LOCKFILE, "--limit", "3"], env=env)

        assert result.exit_code == 0
        assert result.output.startswith("Saved scan: ")

        saved_path = result.output.strip().split("Saved scan: ", 1)[1]
        assert saved_path.endswith(".json")

        parsed = json.loads((tmp_path / "depsly-home" / "scans" / os.path.basename(saved_path)).read_text())
        assert parsed["project"]["name"] == "frontend"
        assert parsed["scan"]["schema_version"] == "1.0"
        assert parsed["scan"]["limit"] == 3
        assert len(parsed["recommendations"]) == 3

    def test_save_scan_respects_no_dev_flag(self, tmp_path):
        runner = CliRunner()
        env = {"DEPSLY_HOME": str(tmp_path / "depsly-home")}

        result = runner.invoke(cli, ["save-scan", LOCKFILE, "--no-dev", "--limit", "2"], env=env)

        assert result.exit_code == 0
        saved_path = result.output.strip().split("Saved scan: ", 1)[1]
        parsed = json.loads((tmp_path / "depsly-home" / "scans" / os.path.basename(saved_path)).read_text())
        assert parsed["scan"]["include_dev"] is False
        assert parsed["scan"]["limit"] == 2
