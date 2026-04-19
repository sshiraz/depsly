"""Tests for the graph-html CLI command."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from click.testing import CliRunner

import cli as cli_module
from cli import cli


class TestGraphHtmlCli:
    def test_graph_html_writes_default_file(self, tmp_path):
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps({
            "name": "app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "app",
                    "version": "1.0.0",
                    "dependencies": {"react": "^18.2.0", "eslint": "^9.0.0"},
                    "devDependencies": {"typescript": "^5.0.0"},
                },
                "node_modules/react": {"version": "18.2.0"},
                "node_modules/eslint": {"version": "9.39.4"},
                "node_modules/typescript": {"version": "5.3.3"},
            },
        }))

        runner = CliRunner()
        result = runner.invoke(cli, ["graph-html", str(lockfile)])

        assert result.exit_code == 0
        output_path = tmp_path / "depsly-graph.html"
        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")
        assert "<title>Depsly Graph • app</title>" in html
        assert "Dependency Graph" in html
        assert "Explorer" in html
        assert "Search package name or version" in html
        assert "Neighborhood" in html
        assert "Box zoom" in html
        assert "Option" in html
        assert "Ctrl" in html
        assert "Use arrow keys to pan" in html
        assert "Path from root" in html
        assert "Direct dev" in html
        assert "react@18.2.0" in html
        assert "eslint@9.39.4" in html
        assert "typescript@5.3.3" in html

    def test_graph_html_respects_custom_output(self, tmp_path):
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
        output_path = tmp_path / "graph" / "custom.html"

        runner = CliRunner()
        result = runner.invoke(cli, ["graph-html", str(lockfile), "--output", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()
        assert f"Graph HTML written to: {output_path}" in result.output

    def test_graph_html_can_request_browser_open(self, tmp_path, monkeypatch):
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
        opened: list[str] = []

        monkeypatch.setattr(cli_module.webbrowser, "open", lambda url: opened.append(url) or True)

        runner = CliRunner()
        result = runner.invoke(cli, ["graph-html", str(lockfile), "--open"])

        assert result.exit_code == 0
        assert len(opened) == 1
        assert opened[0].startswith("file://")
