"""Tests for the trace CLI command."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

from cli import cli


def shared_lockfile():
    return {
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
                "dependencies": {"C": "^1.0.0"},
            },
            "node_modules/C": {
                "version": "1.0.0",
            },
        },
    }


class TestTraceCli:
    def test_trace_direct_dependency(self, tmp_path):
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
                "node_modules/react": {"version": "18.2.0"},
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "react@18.2.0"])
        assert result.exit_code == 0
        assert result.output.startswith("Trace for: react@18.2.0")
        assert "1. app@1.0.0 -> react@18.2.0" in result.output

    def test_trace_transitive_dependency_multiple_paths(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(shared_lockfile()))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "C@1.0.0"])
        assert result.exit_code == 0
        assert "1. app@1.0.0 -> A@1.0.0 -> C@1.0.0" in result.output
        assert "2. app@1.0.0 -> B@1.0.0 -> C@1.0.0" in result.output

    def test_trace_respects_max_paths(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(shared_lockfile()))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "C@1.0.0", "--max-paths", "1"])
        assert result.exit_code == 0
        assert "1. app@1.0.0 -> A@1.0.0 -> C@1.0.0" in result.output
        assert "2. " not in result.output

    def test_trace_json_output(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(shared_lockfile()))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "C@1.0.0", "--max-paths", "1", "--json"])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed["meta"]["command"] == "trace"
        assert parsed["meta"]["schema_version"] == "1.0"
        assert parsed["meta"]["max_paths"] == 1
        assert parsed["result"] == {
            "package_key": "C@1.0.0",
            "package_found": True,
            "reachable_from_root": True,
            "path_count": 1,
            "paths": [["app@1.0.0", "A@1.0.0", "C@1.0.0"]],
        }

    def test_trace_json_missing_package(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(shared_lockfile()))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "missing@0.0.0", "--json"])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed["meta"]["command"] == "trace"
        assert parsed["meta"]["max_paths"] == 3
        assert parsed["result"] == {
            "package_key": "missing@0.0.0",
            "package_found": False,
            "reachable_from_root": False,
            "path_count": 0,
            "paths": [],
        }

    def test_trace_package_not_found(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(shared_lockfile()))

        runner = CliRunner()
        result = runner.invoke(cli, ["trace", str(lockfile), "missing@0.0.0"])
        assert result.exit_code == 0
        assert result.output.strip() == "Package 'missing@0.0.0' not found in the dependency graph."
