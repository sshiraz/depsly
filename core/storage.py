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
