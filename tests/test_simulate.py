"""Tests for core.simulate."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli
from core.graph import build_graph
from core.resolve import resolve_package_key
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

    def test_cli_accepts_bare_package_name(self, tmp_path):
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
        result = runner.invoke(cli, ["simulate-remove", str(lockfile), "react"])
        assert result.exit_code == 0
        assert result.output.startswith("Simulating removal: react@18.2.0")
        assert "Resolved 'react' to 'react@18.2.0'" in result.output

    def test_cli_resolves_multiple_versions_by_direct_dependency_first(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "app",
                    "version": "1.0.0",
                    "dependencies": {"lodash": "^4.17.21", "wrapper": "^1.0.0"},
                },
                "node_modules/lodash": {"version": "4.17.21"},
                "node_modules/wrapper": {
                    "version": "1.0.0",
                    "dependencies": {"lodash": "^3.10.1"},
                },
                "node_modules/wrapper/node_modules/lodash": {"version": "3.10.1"},
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", str(lockfile), "lodash"])
        assert result.exit_code == 0
        assert result.output.startswith("Simulating removal: lodash@4.17.21")
        assert "Resolved 'lodash' to 'lodash@4.17.21'" in result.output

    def test_cli_missing_package_still_errors_cleanly(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "app", "version": "1.0.0"},
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["simulate-remove", str(lockfile), "missing"])
        assert result.exit_code != 0
        assert "Package 'missing' not found in the dependency graph." in result.output


class TestResolvePackageKey:
    def test_exact_key_match_wins(self):
        graph = build_graph(shared_transitive_data())
        assert resolve_package_key(graph, "C@1.0.0") == "C@1.0.0"

    def test_single_name_match_resolves(self):
        graph = build_graph(shared_transitive_data())
        assert resolve_package_key(graph, "C") == "C@1.0.0"

    def test_multiple_versions_prefer_direct_dependency(self):
        data = {
            "root": "app@1.0.0",
            "packages": {
                "app@1.0.0": {
                    "name": "app",
                    "version": "1.0.0",
                    "dependencies": ["lodash@4.17.21", "wrapper@1.0.0"],
                },
                "lodash@4.17.21": {
                    "name": "lodash",
                    "version": "4.17.21",
                    "dependencies": [],
                },
                "wrapper@1.0.0": {
                    "name": "wrapper",
                    "version": "1.0.0",
                    "dependencies": ["lodash@3.10.1"],
                },
                "lodash@3.10.1": {
                    "name": "lodash",
                    "version": "3.10.1",
                    "dependencies": [],
                },
            },
            "root_dev_dependency_keys": (),
        }
        graph = build_graph(data)
        assert resolve_package_key(graph, "lodash", normalized_data=data) == "lodash@4.17.21"
