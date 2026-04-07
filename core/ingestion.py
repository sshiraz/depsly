"""Parse package-lock.json (v3) into the normalized format expected by build_graph().

Known limitation (P0 tech debt):
    name_to_key maps package name -> single installed version. npm allows
    multiple versions of the same package (e.g. react@18.2.0 and react@17.0.2).
    The current implementation will silently overwrite, keeping only the last
    version seen. This must be fixed before multi-version resolution is needed.
"""

from __future__ import annotations

import json
from pathlib import Path


class IngestionError(Exception):
    """Raised when a lockfile cannot be parsed."""


def parse_package_lock(
    lockfile: str | Path,
    *,
    include_dev: bool = True,
) -> dict:
    """Parse a package-lock.json file and return normalized graph input.

    Supports lockfileVersion 2 and 3 (npm v7+). The returned dict is ready
    to pass directly to build_graph().

    Args:
        lockfile: Path to package-lock.json, or its contents as a string.
        include_dev: Whether to include devDependencies for the root package.
            True by default — set to False for production-only analysis.

    Returns:
        Normalized dict with "root" and "packages" keys.
    """
    if isinstance(lockfile, Path) or (isinstance(lockfile, str) and not lockfile.lstrip().startswith("{")):
        path = Path(lockfile)
        if not path.exists():
            raise IngestionError(f"File not found: {path}")
        raw = json.loads(path.read_text())
    else:
        raw = json.loads(lockfile)

    lockfile_version = raw.get("lockfileVersion")
    if lockfile_version not in (2, 3):
        raise IngestionError(
            f"Unsupported lockfileVersion: {lockfile_version}. Expected 2 or 3."
        )

    packages = raw.get("packages", {})
    if not isinstance(packages, dict):
        raise IngestionError("'packages' field must be a dict")

    return _normalize_v3(packages, include_dev=include_dev)


def _normalize_v3(packages: dict, *, include_dev: bool) -> dict:
    """Convert lockfile v3 packages map to normalized graph input.

    Lockfile v3 keys are paths like "" (root) and "node_modules/react".
    Dependencies are name->semver-range maps that need to be resolved
    to the actual installed name@version.
    """
    if "" not in packages:
        raise IngestionError("Lockfile has no root entry (empty string key in packages)")

    # Pass 1: build a lookup from package name -> installed key (name@version)
    # and collect all normalized entries
    name_to_key: dict[str, str] = {}
    normalized: dict[str, dict] = {}
    root_key: str | None = None
    root_dev_dependency_names: set[str] = set()

    for path, info in packages.items():
        name = info.get("name") or _name_from_path(path)
        version = info.get("version", "0.0.0")

        if not name:
            continue

        key = f"{name}@{version}"

        if path == "":
            root_key = key
            root_dev_dependency_names = set(info.get("devDependencies", {}))

        name_to_key[name] = key

        raw_deps = dict(info.get("dependencies", {}))
        if path == "" and include_dev:
            raw_deps.update(info.get("devDependencies", {}))

        normalized[key] = {
            "name": name,
            "version": version,
            "_raw_deps": raw_deps,
        }

    # Pass 2: resolve dependency names to installed keys
    for key, entry in normalized.items():
        raw_deps = entry.pop("_raw_deps")
        resolved = []
        unresolved = []
        for dep_name in raw_deps:
            dep_key = name_to_key.get(dep_name)
            if dep_key is not None:
                resolved.append(dep_key)
            else:
                unresolved.append(dep_name)
        entry["dependencies"] = resolved
        if unresolved:
            entry["unresolved_dependencies"] = unresolved

    root_dev_dependency_keys = tuple(
        sorted(
            name_to_key[dep_name]
            for dep_name in root_dev_dependency_names
            if dep_name in name_to_key
        )
    )

    return {
        "root": root_key,
        "packages": normalized,
        "root_dev_dependency_keys": root_dev_dependency_keys,
    }


def _name_from_path(path: str) -> str:
    """Extract package name from a node_modules path.

    "node_modules/@babel/core" -> "@babel/core"
    "node_modules/react" -> "react"
    """
    prefix = "node_modules/"
    if not path.startswith(prefix):
        return ""
    return path[len(prefix):]
