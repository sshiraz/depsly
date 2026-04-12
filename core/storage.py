"""Local persistence helpers for saved Depsly scans."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


def depsly_home() -> Path:
    """Return the local Depsly home directory."""
    configured = os.environ.get("DEPSLY_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".depsly"


def scans_dir() -> Path:
    """Return the local directory used for persisted scan outputs."""
    return depsly_home() / "scans"


def project_slug(project_name: str) -> str:
    """Normalize a project name into a stable filename slug."""
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name.strip().lower()).strip("-")
    return normalized or "unknown-project"


def scan_filename(project_name: str, timestamp: str) -> str:
    """Build the canonical filename for a persisted scan."""
    safe_timestamp = timestamp.replace(":", "-")
    return f"{project_slug(project_name)}-{safe_timestamp}.json"


def save_scan_export(export_data: dict) -> Path:
    """Persist a normalized scan export and return the written path."""
    project_name = export_data["project"]["name"]
    timestamp = export_data["scan"]["timestamp"]
    output_dir = scans_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / scan_filename(project_name, timestamp)
    output_path.write_text(json.dumps(export_data, indent=2) + "\n", encoding="utf-8")
    return output_path


def list_saved_scans(project_name: str | None = None) -> list[Path]:
    """List saved scan files in deterministic timestamp order."""
    output_dir = scans_dir()
    if not output_dir.exists():
        return []

    if project_name:
        pattern = f"{project_slug(project_name)}-*.json"
        paths = list(output_dir.glob(pattern))
    else:
        paths = list(output_dir.glob("*.json"))

    return sorted(paths)


def load_scan_export(path: Path) -> dict:
    """Load a saved scan export from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def compare_scan_exports(before: dict, after: dict) -> dict:
    """Compute a small deterministic diff between two saved scan exports."""
    before_project = before["project"]
    after_project = after["project"]
    before_recommendations = before["recommendations"]
    after_recommendations = after["recommendations"]

    before_top = before_recommendations[0]["package_key"] if before_recommendations else None
    after_top = after_recommendations[0]["package_key"] if after_recommendations else None

    return {
        "project": {
            "before": before_project["name"],
            "after": after_project["name"],
        },
        "scan": {
            "before_timestamp": before["scan"]["timestamp"],
            "after_timestamp": after["scan"]["timestamp"],
        },
        "dependencies": {
            "before_total": before_project["total_dependencies"],
            "after_total": after_project["total_dependencies"],
            "delta_total": after_project["total_dependencies"] - before_project["total_dependencies"],
            "before_direct": before_project["direct_dependencies"],
            "after_direct": after_project["direct_dependencies"],
            "delta_direct": after_project["direct_dependencies"] - before_project["direct_dependencies"],
            "before_transitive": before_project["transitive_dependencies"],
            "after_transitive": after_project["transitive_dependencies"],
            "delta_transitive": (
                after_project["transitive_dependencies"] - before_project["transitive_dependencies"]
            ),
            "before_max_depth": before_project["max_depth"],
            "after_max_depth": after_project["max_depth"],
            "delta_max_depth": after_project["max_depth"] - before_project["max_depth"],
        },
        "recommendations": {
            "before_top": before_top,
            "after_top": after_top,
            "changed": before_top != after_top,
        },
    }
