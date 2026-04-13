"""Tests for the batch scan script entrypoint."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scan_repos.py"
LOCKFILE = ROOT / "frontend" / "package-lock.json"


def test_scan_repos_script_dry_run(tmp_path):
    repo = tmp_path / "frontend-copy"
    repo.mkdir()
    (repo / "package-lock.json").write_text(LOCKFILE.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(repo), "--output-dir", str(tmp_path / "out"), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "DEPSLY_HOME": str(tmp_path / "depsly-home")},
        check=False,
    )

    assert result.returncode == 0
    assert "DRY_RUN" in result.stdout
    assert "Summary: saved=1 skipped=0 failed=0" in result.stdout
