"""Tests for human-readable analyze CLI output."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli


class TestAnalyzeCli:
    def test_analyze_includes_model_signal_and_impact_signal(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "nextjs-test", "package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "Top Recommendation" in result.output
        assert "(ranked by risk model)" in result.output
        assert "biggest structural impact" in result.output.lower()
        assert "Proof:" in result.output
        assert "Before:" in result.output
        assert "After removing" in result.output
        assert "Why this matters:" in result.output
        assert "Recommended action:" in result.output

    def test_analyze_includes_trace_and_disclaimer_in_hero_block(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "nextjs-test", "package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "Trace:" in result.output
        assert "Heuristic-based analysis. Validate with tests." in result.output

    def test_blast_radius_labels_direct_and_transitive(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "app",
                    "version": "1.0.0",
                    "dependencies": {"A": "^1.0.0", "B": "^1.0.0"},
                },
                "node_modules/A": {
                    "version": "1.0.0",
                    "dependencies": {"C": "^1.0.0"},
                },
                "node_modules/B": {
                    "version": "1.0.0",
                },
                "node_modules/C": {
                    "version": "1.0.0",
                },
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(lockfile)])
        assert result.exit_code == 0
        assert "[direct]" in result.output
        assert "[transitive]" in result.output

    def test_analyze_includes_next_step_hints(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "Next steps:" in result.output
        assert "depsly recommend" in result.output
        assert "depsly trace" in result.output

    def test_analyze_explains_transitive_packages_need_tracing(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "frontend", "package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "transitive packages often need tracing upstream" in result.output

    def test_analyze_clarifies_graph_vs_root_reachable_counts(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "axios-test", "axios-package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "Graph nodes:" in result.output
        assert "Root-reachable direct:" in result.output
        assert "Root-reachable transitive:" in result.output
        assert "Root-reachable total:" in result.output

    def test_analyze_uses_moderate_concentration_wording_when_not_high(self):
        lockfile = os.path.join(os.path.dirname(__file__), "..", "axios-test", "axios-package-lock.json")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", lockfile])
        assert result.exit_code == 0
        assert "Moderate concentration:" in result.output
        assert "High centralization:" not in result.output
