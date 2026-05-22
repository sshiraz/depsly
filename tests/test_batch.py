"""Tests for batch scan helpers."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.batch import (
    batch_output_filename,
    batch_output_path,
    find_lockfile,
    read_manifest,
    scan_repo_to_output,
)


LOCKFILE = Path(os.path.dirname(__file__)) / ".." / "frontend" / "package-lock.json"


def test_find_lockfile_prefers_repo_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root_lockfile = repo / "package-lock.json"
    nested_dir = repo / "frontend"
    nested_dir.mkdir()
    nested_lockfile = nested_dir / "package-lock.json"
    root_lockfile.write_text("{}")
    nested_lockfile.write_text("{}")

    assert find_lockfile(repo) == root_lockfile


def test_find_lockfile_falls_back_to_first_nested_path(tmp_path):
    repo = tmp_path / "repo"
    (repo / "b").mkdir(parents=True)
    (repo / "a").mkdir(parents=True)
    lock_b = repo / "b" / "package-lock.json"
    lock_a = repo / "a" / "package-lock.json"
    lock_b.write_text("{}")
    lock_a.write_text("{}")

    assert find_lockfile(repo) == lock_a


def test_find_lockfile_accepts_root_yarn_lock(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    lockfile = repo / "yarn.lock"
    lockfile.write_text("# yarn lockfile v1\n")
    assert find_lockfile(repo) == lockfile


def test_batch_output_filename_is_deterministic(tmp_path):
    repo = tmp_path / "My Repo"
    repo.mkdir()
    first = batch_output_filename(repo)
    second = batch_output_filename(repo)
    assert first == second
    assert first.endswith(".json")


def test_batch_output_path_uses_output_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    output_dir = tmp_path / "out"
    assert batch_output_path(repo, output_dir).parent == output_dir


def test_read_manifest_skips_comments_and_blank_lines(tmp_path):
    manifest = tmp_path / "repos.txt"
    manifest.write_text("# comment\n\n~/a\n~/b\n", encoding="utf-8")
    paths = read_manifest(manifest)
    assert paths == [Path("~/a").expanduser(), Path("~/b").expanduser()]


def test_scan_repo_to_output_skips_missing_lockfile(tmp_path):
    repo = tmp_path / "missing"
    repo.mkdir()
    result = scan_repo_to_output(repo, output_dir=tmp_path / "out", dry_run=True)
    assert result["status"] == "skipped"
    assert result["reason"] == "missing_lockfile"


def test_scan_repo_to_output_dry_run_reports_target(tmp_path):
    repo = tmp_path / "frontend-copy"
    repo.mkdir()
    (repo / "package-lock.json").write_text(LOCKFILE.read_text(encoding="utf-8"), encoding="utf-8")

    result = scan_repo_to_output(repo, output_dir=tmp_path / "out", dry_run=True)

    assert result["status"] == "dry_run"
    assert result["lockfile"].endswith("package-lock.json")
    assert result["output"].endswith(".json")


def test_scan_repo_to_output_writes_export(tmp_path):
    repo = tmp_path / "frontend-copy"
    repo.mkdir()
    (repo / "package-lock.json").write_text(LOCKFILE.read_text(encoding="utf-8"), encoding="utf-8")
    output_dir = tmp_path / "out"

    result = scan_repo_to_output(repo, output_dir=output_dir, include_dev=False, limit=2)

    assert result["status"] == "saved"
    output_path = Path(result["output"])
    assert output_path.exists()
    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert parsed["project"]["name"] == "frontend"
    assert parsed["scan"]["include_dev"] is False
    assert parsed["scan"]["limit"] == 2
