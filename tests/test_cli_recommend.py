"""Tests for the recommend CLI command."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli


LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")


class TestRecommendCli:
    def test_recommend_command_runs(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "3"])
        assert result.exit_code == 0
        assert result.output.startswith("Depsly Recommendations")

    def test_recommend_output_contains_expected_fields(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "1"])
        assert result.exit_code == 0
        assert "Project: frontend" in result.output
        assert "Packages analyzed:" in result.output
        assert "Scoring version: v1" in result.output
        assert "Recommended focus:" in result.output
        assert "Summary:" in result.output
        assert "Action:" in result.output
        assert "Actionability:" in result.output
        assert "Reason confidence:" in result.output
        assert "Impact:" in result.output
        assert "Classification:" in result.output
        assert "Why:" in result.output
        assert "Next steps:" in result.output
        assert f"depsly trace {LOCKFILE}" in result.output
        assert f"depsly simulate-remove {LOCKFILE}" in result.output

    def test_recommend_output_is_stably_ordered(self):
        runner = CliRunner()
        r1 = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "5"])
        r2 = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "5"])
        assert r1.exit_code == 0
        assert r2.exit_code == 0
        assert r1.output == r2.output

    def test_recommend_respects_limit(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "2"])
        assert result.exit_code == 0
        assert "\n1. " in result.output
        assert "\n2. " in result.output
        assert "\n3. " not in result.output

    def test_recommend_empty_graph(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "empty-app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "empty-app",
                    "version": "1.0.0",
                },
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", str(lockfile)])
        assert result.exit_code == 0
        assert result.output.strip() == "No package recommendations available."

    def test_defer_actionability_is_clarified(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        packages = {
            "": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": {
                    "tiny": "^1.0.0",
                    "big": "^1.0.0",
                },
            },
            "node_modules/tiny": {
                "version": "1.0.0",
            },
            "node_modules/big": {
                "version": "1.0.0",
                "dependencies": {"big-1": "^1.0.0"},
            },
        }
        for index in range(1, 21):
            key = f"node_modules/big-{index}"
            entry = {"version": "1.0.0"}
            if index < 20:
                entry["dependencies"] = {f"big-{index + 1}": "^1.0.0"}
            packages[key] = entry

        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": packages,
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", str(lockfile), "--limit", "30"])
        assert result.exit_code == 0
        assert "Action: DEFER" in result.output
        assert "Actionability: HIGH (low impact)" in result.output

    def test_recommend_why_includes_concrete_impact_language(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "1"])
        assert result.exit_code == 0
        assert "Structural impact:" in result.output
        assert "Verify whether this dependency is still required" in result.output or "still required before removing it" in result.output

    def test_non_dev_direct_dependency_is_not_presented_as_remove(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "app",
                    "version": "1.0.0",
                    "dependencies": {"react": "^18.2.0"},
                },
                "node_modules/react": {
                    "version": "18.2.0",
                    "dependencies": {
                        "scheduler": "^0.23.0",
                        "loose-envify": "^1.4.0",
                    },
                },
                "node_modules/scheduler": {"version": "0.23.0"},
                "node_modules/loose-envify": {"version": "1.4.0"},
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", str(lockfile), "--limit", "1"])
        assert result.exit_code == 0
        assert "Action: REMOVE" not in result.output

    def test_recommend_uses_polished_classification_labels(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "1"])
        assert result.exit_code == 0
        assert "Classification: Direct (root dev dependency)" in result.output

    def test_recommend_marks_top_priority_items(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "2"])
        assert result.exit_code == 0
        assert result.output.count("Priority: HIGH") >= 1

    def test_recommend_summary_mentions_upstream_change(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "5"])
        assert result.exit_code == 0
        assert "transitive dependency requires upstream change" in result.output

    def test_recommend_summary_uses_high_impact_recommendations_language(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "axios-test", "axios-package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", lockfile, "--limit", "10"])
        assert result.exit_code == 0
        assert "high-impact recommendation" in result.output
        assert "0 high-impact dependencies worth reviewing" not in result.output
