"""Batch scan helpers for multiple repository paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.scan import build_recommendation_scan
from core.storage import depsly_home, project_slug


def batch_scans_dir() -> Path:
    """Return the default output directory for batch scan exports."""
    return depsly_home() / "batch-scans"


def find_lockfile(repo_path: Path) -> Path | None:
    """Locate a package-lock.json for a repository path deterministically."""
    root_candidate = repo_path / "package-lock.json"
    if root_candidate.exists():
        return root_candidate

    candidates: list[Path] = []
    for path in repo_path.rglob("package-lock.json"):
        parts = set(path.parts)
        if ".git" in parts or "node_modules" in parts or "venv" in parts:
            continue
        candidates.append(path)

    if not candidates:
        return None

    return sorted(candidates, key=lambda path: (len(path.relative_to(repo_path).parts), str(path.relative_to(repo_path))))[0]


def batch_output_filename(repo_path: Path) -> str:
    """Build a deterministic per-repo output filename."""
    resolved = str(repo_path.resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:8]
    return f"{project_slug(repo_path.name)}-{digest}.json"


def batch_output_path(repo_path: Path, output_dir: Path | None = None) -> Path:
    """Return the deterministic output path for a repo scan."""
    target_dir = output_dir or batch_scans_dir()
    return target_dir / batch_output_filename(repo_path)


def read_manifest(manifest_path: Path) -> list[Path]:
    """Read a manifest file containing one repo path per line."""
    paths: list[Path] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(Path(line).expanduser())
    return paths


def scan_repo_to_output(
    repo_path: Path,
    *,
    output_dir: Path | None = None,
    include_dev: bool = True,
    limit: int = 10,
    dry_run: bool = False,
) -> dict:
    """Scan a single repo path and write a normalized export when possible."""
    repo_path = repo_path.expanduser()
    lockfile = find_lockfile(repo_path)
    if lockfile is None:
        return {
            "repo": str(repo_path),
            "status": "skipped",
            "reason": "missing_lockfile",
        }

    destination = batch_output_path(repo_path, output_dir)
    if dry_run:
        return {
            "repo": str(repo_path),
            "lockfile": str(lockfile),
            "output": str(destination),
            "status": "dry_run",
        }

    export_data = build_recommendation_scan(lockfile, include_dev=include_dev, limit=limit)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(export_data, indent=2) + "\n", encoding="utf-8")
    return {
        "repo": str(repo_path),
        "lockfile": str(lockfile),
        "output": str(destination),
        "status": "saved",
    }
