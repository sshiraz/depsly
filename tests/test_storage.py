"""Tests for local scan persistence helpers."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.storage import depsly_home, project_slug, save_scan_export, scan_filename, scans_dir


def test_depsly_home_uses_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "custom-home"))
    assert depsly_home() == tmp_path / "custom-home"
    assert scans_dir() == tmp_path / "custom-home" / "scans"


def test_project_slug_normalizes_names():
    assert project_slug("Next App Test") == "next-app-test"
    assert project_slug("@Scope/Thing") == "scope-thing"


def test_scan_filename_is_stable():
    assert (
        scan_filename("Next App Test", "2026-04-11T10:15:43Z")
        == "next-app-test-2026-04-11T10-15-43Z.json"
    )


def test_save_scan_export_writes_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    export_data = {
        "project": {"name": "frontend"},
        "recommendations": [],
        "top_blast_radius": [],
        "scan": {
            "timestamp": "2026-04-11T10:15:43Z",
            "schema_version": "1.0",
        },
    }

    output_path = save_scan_export(export_data)

    assert output_path == tmp_path / "depsly-home" / "scans" / "frontend-2026-04-11T10-15-43Z.json"
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == export_data
