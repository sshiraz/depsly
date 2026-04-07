"""Tests for core.simulate."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli
from core.graph import build_graph
from core.simulate import simulate_remove


def shared_transitive_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {"name": "app", "version": "1.0.0", "dependencies": ["A@1.0.0", "B@1.0.0"]},
            "A@1.0.0": {"name": "A", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "B@1.0.0": {"name": "B", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "C@1.0.0": {"name": "C", "version": "1.0.0", "dependencies": ["D@1.0.0"]},
            "D@1.0.0": {"name": "D", "version": "1.0.0", "dependencies": []},
        },
    }

class TestSimulateRemove:
    def test_result_shape_and_counts(self):
        graph = build_graph(shared_transitive_data())
        result = simulate_remove(graph, "C@1.0.0")
        assert result.package_key == "C@1.0.0"
        assert result.package_found is True
        assert result.removed_keys == ("C@1.0.0", "D@1.0.0")
        assert result.removed_count == 2
        assert result.total_nodes_before == 5
        assert result.total_nodes_after == 3
        assert result.percent_removed == 2 / 5
        assert result.impacted_packages == (("A@1.0.0", 2), ("B@1.0.0", 2))

    def test_missing_package(self):
        graph = build_graph(shared_transitive_data())
        result = simulate_remove(graph, "missing@0.0.0")
        assert result.package_found is False
        assert result.removed_keys == ()
        assert result.removed_count == 0
        assert result.total_nodes_before == 5
        assert result.total_nodes_after == 5
        assert result.percent_removed == 0.0
        assert result.impacted_packages == ()

    def test_empty_graph(self):
        graph = build_graph({"root": "missing@1.0.0", "packages": {}})
        result = simulate_remove(graph, "missing@1.0.0")
        assert result.package_found is False
        assert result.removed_keys == ()
        assert result.removed_count == 0
        assert result.total_nodes_before == 0
        assert result.total_nodes_after == 0
        assert result.percent_removed == 0.0


class TestSimulateRemoveCli:
    def test_cli_output_shape_unchanged(self, tmp_path):
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
                },
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", str(lockfile), "react@18.2.0"])
        assert result.exit_code == 0
        assert result.output.startswith("Simulating removal: react@18.2.0")
        assert "Before:" in result.output
        assert "After:" in result.output
        assert "Impact:" in result.output
        assert "Structural simulation only." in result.output
