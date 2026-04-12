"""Tests for local scan persistence helpers."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.storage import (
    compare_scan_exports,
    depsly_home,
    list_saved_scans,
    load_scan_export,
    project_slug,
    save_scan_export,
    scan_filename,
    scans_dir,
)


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


def test_list_saved_scans_is_sorted_and_filterable(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    first = {
        "project": {"name": "frontend"},
        "recommendations": [],
        "top_blast_radius": [],
        "scan": {"timestamp": "2026-04-11T10:15:43Z", "schema_version": "1.0"},
    }
    second = {
        "project": {"name": "frontend"},
        "recommendations": [],
        "top_blast_radius": [],
        "scan": {"timestamp": "2026-04-12T08:00:00Z", "schema_version": "1.0"},
    }
    other = {
        "project": {"name": "other-app"},
        "recommendations": [],
        "top_blast_radius": [],
        "scan": {"timestamp": "2026-04-13T08:00:00Z", "schema_version": "1.0"},
    }

    save_scan_export(second)
    save_scan_export(other)
    save_scan_export(first)

    all_paths = list_saved_scans()
    assert [path.name for path in all_paths] == [
        "frontend-2026-04-11T10-15-43Z.json",
        "frontend-2026-04-12T08-00-00Z.json",
        "other-app-2026-04-13T08-00-00Z.json",
    ]

    filtered = list_saved_scans("frontend")
    assert [path.name for path in filtered] == [
        "frontend-2026-04-11T10-15-43Z.json",
        "frontend-2026-04-12T08-00-00Z.json",
    ]


def test_load_scan_export_round_trips_saved_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPSLY_HOME", str(tmp_path / "depsly-home"))
    export_data = {
        "project": {"name": "frontend"},
        "recommendations": [{"package_key": "a@1.0.0"}],
        "top_blast_radius": [],
        "scan": {"timestamp": "2026-04-11T10:15:43Z", "schema_version": "1.0"},
    }
    output_path = save_scan_export(export_data)
    assert load_scan_export(output_path) == export_data


def test_compare_scan_exports_computes_small_stable_diff():
    before = {
        "project": {
            "name": "frontend",
            "total_dependencies": 100,
            "direct_dependencies": 10,
            "transitive_dependencies": 90,
            "max_depth": 7,
        },
        "recommendations": [{"package_key": "eslint@9.0.0"}],
        "scan": {"timestamp": "2026-04-11T10:15:43Z"},
    }
    after = {
        "project": {
            "name": "frontend",
            "total_dependencies": 92,
            "direct_dependencies": 9,
            "transitive_dependencies": 83,
            "max_depth": 5,
        },
        "recommendations": [{"package_key": "vite@8.0.0"}],
        "scan": {"timestamp": "2026-04-12T10:15:43Z"},
    }

    comparison = compare_scan_exports(before, after)

    assert comparison["dependencies"]["delta_total"] == -8
    assert comparison["dependencies"]["delta_direct"] == -1
    assert comparison["dependencies"]["delta_transitive"] == -7
    assert comparison["dependencies"]["delta_max_depth"] == -2
    assert comparison["recommendations"]["before_top"] == "eslint@9.0.0"
    assert comparison["recommendations"]["after_top"] == "vite@8.0.0"
    assert comparison["recommendations"]["changed"] is True
