"""Tests for CLI --json output."""

import json
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner
from cli import cli


LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")


class TestAnalyzeJson:
    def test_valid_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_expected_top_level_keys(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        expected = {
            "project",
            "risk",
            "dependencies",
            "flags",
            "top_packages_by_fanout",
            "top_packages_by_blast_radius",
        }
        assert set(parsed.keys()) == expected

    def test_risk_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        risk = parsed["risk"]
        assert isinstance(risk["score"], int)
        assert risk["label"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert isinstance(risk["components"], list)
        for comp in risk["components"]:
            assert "category" in comp
            assert "points" in comp
            assert "reason" in comp

    def test_no_ansi_codes(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        # ANSI escape codes start with \x1b[
        assert "\x1b[" not in result.output
        # Also check via regex
        assert not re.search(r"\x1b\[[\d;]*m", result.output)

    def test_dependencies_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        deps = parsed["dependencies"]
        assert isinstance(deps["total"], int)
        assert isinstance(deps["direct"], int)
        assert isinstance(deps["transitive"], int)
        assert isinstance(deps["max_depth"], int)

    def test_human_output_unchanged(self):
        """Without --json, output should NOT be JSON."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE])
        assert result.exit_code == 0
        assert result.output.startswith("Project Risk:")
