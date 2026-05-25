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
            "meta",
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

    def test_meta_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        meta = parsed["meta"]
        assert meta["command"] == "analyze"
        assert meta["schema_version"] == "1.0"
        assert meta["tool_version"] == "0.1.11"
        assert meta["include_dev"] is True
        assert meta["fanout_limit"] == 10
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", meta["timestamp"])

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


class TestRecommendJson:
    def test_valid_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_expected_top_level_keys(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        assert list(parsed.keys()) == ["project", "recommendations", "top_blast_radius", "scan"]

    def test_project_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json"])
        parsed = json.loads(result.output)
        project = parsed["project"]
        assert project["name"] == "frontend"
        assert project["ecosystem"] == "npm"
        assert project["lockfile"] == LOCKFILE
        assert isinstance(project["total_dependencies"], int)
        assert isinstance(project["direct_dependencies"], int)
        assert isinstance(project["transitive_dependencies"], int)
        assert isinstance(project["max_depth"], int)

    def test_recommendation_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "1"])
        parsed = json.loads(result.output)
        recommendation = parsed["recommendations"][0]
        assert list(recommendation.keys()) == [
            "package",
            "version",
            "package_key",
            "action",
            "actionability",
            "reason_confidence",
            "impact_score",
            "impact_percent",
            "feasibility_score",
            "final_score",
            "priority",
            "classification",
            "reasons",
        ]
        assert recommendation["action"] in ("REMOVE", "TRACE_UPSTREAM", "REVIEW", "DEFER")
        assert recommendation["actionability"] in ("HIGH", "MEDIUM", "LOW")
        assert recommendation["reason_confidence"] in ("HIGH", "MEDIUM", "LOW")
        assert recommendation["priority"] in ("HIGH", "NORMAL")
        assert isinstance(recommendation["reasons"], list)
        assert isinstance(recommendation["classification"], dict)
        assert recommendation["package_key"] == f'{recommendation["package"]}@{recommendation["version"]}'

    def test_scan_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "3"])
        parsed = json.loads(result.output)
        scan = parsed["scan"]
        assert scan["schema_version"] == "1.0"
        assert scan["scoring_version"] == "v1"
        assert scan["tool_version"] == "0.1.11"
        assert scan["include_dev"] is True
        assert scan["limit"] == 3
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", scan["timestamp"])

    def test_ordering_is_deterministic_ignoring_timestamp(self):
        runner = CliRunner()
        r1 = json.loads(runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "5"]).output)
        r2 = json.loads(runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "5"]).output)
        assert r1["project"] == r2["project"]
        assert r1["recommendations"] == r2["recommendations"]
        assert r1["top_blast_radius"] == r2["top_blast_radius"]
        assert r1["scan"]["schema_version"] == r2["scan"]["schema_version"]
        assert r1["scan"]["scoring_version"] == r2["scan"]["scoring_version"]
        assert r1["scan"]["tool_version"] == r2["scan"]["tool_version"]
        assert r1["scan"]["include_dev"] == r2["scan"]["include_dev"]
        assert r1["scan"]["limit"] == r2["scan"]["limit"]

    def test_recommendations_are_explicitly_sorted_by_final_score_then_package_key(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "5"])
        parsed = json.loads(result.output)
        recommendations = parsed["recommendations"]
        expected = sorted(
            recommendations,
            key=lambda item: (-item["final_score"], item["package_key"]),
        )
        assert recommendations == expected

    def test_top_blast_radius_package_keys_are_canonical(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json", "--limit", "1"])
        parsed = json.loads(result.output)
        item = parsed["top_blast_radius"][0]
        assert item["package_key"] == f'{item["package"]}@{item["version"]}'

    def test_no_ansi_codes(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--json"])
        assert "\x1b[" not in result.output
        assert not re.search(r"\x1b\[[\d;]*m", result.output)

    def test_human_output_unchanged(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["recommend", LOCKFILE, "--limit", "1"])
        assert result.exit_code == 0
        assert result.output.startswith("Depsly Recommendations")


class TestTraceJson:
    def test_valid_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["trace", LOCKFILE, "react@19.1.1", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_expected_top_level_keys(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["trace", LOCKFILE, "react@19.1.1", "--json"])
        parsed = json.loads(result.output)
        assert list(parsed.keys()) == [
            "meta",
            "result",
        ]

    def test_meta_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["trace", LOCKFILE, "react@19.1.1", "--json"])
        parsed = json.loads(result.output)
        meta = parsed["meta"]
        assert meta["command"] == "trace"
        assert meta["schema_version"] == "1.0"
        assert meta["tool_version"] == "0.1.11"
        assert meta["include_dev"] is True
        assert meta["max_paths"] == 3
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", meta["timestamp"])

    def test_no_ansi_codes(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["trace", LOCKFILE, "react@19.1.1", "--json"])
        assert "\x1b[" not in result.output
        assert not re.search(r"\x1b\[[\d;]*m", result.output)


class TestSimulateRemoveJson:
    def test_valid_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", LOCKFILE, "react", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_expected_top_level_keys(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", LOCKFILE, "react", "--json"])
        parsed = json.loads(result.output)
        assert list(parsed.keys()) == [
            "meta",
            "result",
        ]

    def test_before_after_shape(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", LOCKFILE, "react", "--json"])
        parsed = json.loads(result.output)
        for phase in ("before", "after"):
            report = parsed["result"][phase]
            assert list(report.keys()) == [
                "total_nodes",
                "total_edges",
                "max_depth",
                "has_cycle",
                "direct_dependency_count",
                "transitive_dependency_count",
                "unresolved_dependency_count",
                "leaf_package_count",
                "top_packages_by_fanout",
                "top_packages_by_blast_radius",
            ]

    def test_meta_structure(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", LOCKFILE, "react", "--json"])
        parsed = json.loads(result.output)
        meta = parsed["meta"]
        assert meta["command"] == "simulate-remove"
        assert meta["schema_version"] == "1.0"
        assert meta["tool_version"] == "0.1.11"
        assert meta["include_dev"] is True
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", meta["timestamp"])

    def test_no_ansi_codes(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", LOCKFILE, "react", "--json"])
        assert "\x1b[" not in result.output
        assert not re.search(r"\x1b\[[\d;]*m", result.output)
