"""Parse package-lock.json (v3) into the normalized format expected by build_graph().

Resolution model:
    npm allows the same package name to appear at multiple versions (e.g.
    react@18.2.0 at node_modules/react and react@17.0.2 nested under
    node_modules/some-pkg/node_modules/react). Dependency edges are
    resolved by walking up the lockfile path tree from the dependent,
    matching Node.js module resolution: a dep declared at path P is
    looked up first at P/node_modules/<dep>, then at the closest ancestor
    that has node_modules/<dep>, finally falling back to the top-level
    node_modules/<dep>. This preserves multi-version installs as distinct
    graph nodes.
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
    Dependencies are name->semver-range maps that need to be resolved to
    the actual installed name@version. Resolution walks up from the
    dependent's path so nested installs preserve their distinct version.
    """
    if "" not in packages:
        raise IngestionError("Lockfile has no root entry (empty string key in packages)")

    # Pass 1: assign a name@version key to every path entry.
    path_to_key: dict[str, str] = {}
    root_key: str | None = None
    root_dev_dependency_names: set[str] = set()

    for path, info in packages.items():
        name = info.get("name") or _name_from_path(path)
        if not name:
            continue
        version = info.get("version", "0.0.0")
        key = f"{name}@{version}"
        path_to_key[path] = key
        if path == "":
            root_key = key
            root_dev_dependency_names = set(info.get("devDependencies", {}))

    # Pass 2: build one normalized entry per unique key. When a key is
    # installed at multiple paths (rare but legal — e.g. when npm dedupes),
    # union edges from each occurrence.
    normalized: dict[str, dict] = {}

    for path, info in packages.items():
        key = path_to_key.get(path)
        if key is None:
            continue

        if key not in normalized:
            normalized[key] = {
                "name": info.get("name") or _name_from_path(path),
                "version": info.get("version", "0.0.0"),
                "dependencies": [],
                "install_paths": [],
                "_seen": set(),
                "_unresolved": [],
            }
        entry = normalized[key]
        entry["install_paths"].append(path)

        raw_deps = dict(info.get("dependencies", {}))
        if path == "" and include_dev:
            raw_deps.update(info.get("devDependencies", {}))

        for dep_name in raw_deps:
            dep_path = _resolve_dep_path(path, dep_name, packages)
            if dep_path is None:
                entry["_unresolved"].append(dep_name)
                continue
            dep_key = path_to_key.get(dep_path)
            if dep_key is None:
                entry["_unresolved"].append(dep_name)
                continue
            if dep_key not in entry["_seen"]:
                entry["_seen"].add(dep_key)
                entry["dependencies"].append(dep_key)

    for entry in normalized.values():
        entry.pop("_seen", None)
        unresolved = entry.pop("_unresolved")
        if unresolved:
            entry["unresolved_dependencies"] = sorted(set(unresolved))
        entry["install_paths"] = sorted(set(entry["install_paths"]))

    root_dev_keys: list[str] = []
    for dep_name in root_dev_dependency_names:
        dep_path = _resolve_dep_path("", dep_name, packages)
        if dep_path is None:
            continue
        dep_key = path_to_key.get(dep_path)
        if dep_key is not None:
            root_dev_keys.append(dep_key)

    return {
        "root": root_key,
        "packages": normalized,
        "root_dev_dependency_keys": tuple(sorted(set(root_dev_keys))),
    }


def _resolve_dep_path(
    dependent_path: str,
    dep_name: str,
    packages: dict,
) -> str | None:
    """Find the lockfile path that resolves dep_name from dependent_path.

    Implements npm's module resolution: search dependent_path's
    node_modules first, then walk up by stripping trailing
    /node_modules/<segment> hops, falling back to top-level node_modules.

    Workspace-style entries with `link: true` are followed once via
    their `resolved` field to the canonical entry.
    """
    search_prefixes: list[str] = [dependent_path]
    current = dependent_path
    marker = "/node_modules/"
    while current:
        idx = current.rfind(marker)
        if idx == -1:
            if current != "":
                search_prefixes.append("")
            break
        current = current[:idx]
        search_prefixes.append(current)

    for prefix in search_prefixes:
        candidate = (
            f"{prefix}/node_modules/{dep_name}"
            if prefix
            else f"node_modules/{dep_name}"
        )
        if candidate not in packages:
            continue
        entry = packages[candidate]
        if entry.get("link") and isinstance(entry.get("resolved"), str):
            target = entry["resolved"]
            if target in packages:
                return target
        return candidate
    return None


def _name_from_path(path: str) -> str:
    """Extract package name from a node_modules path.

    "node_modules/@babel/core" -> "@babel/core"
    "node_modules/react" -> "react"
    Nested: "node_modules/foo/node_modules/bar" -> "bar"
            "node_modules/foo/node_modules/@scope/bar" -> "@scope/bar"
    """
    marker = "/node_modules/"
    idx = path.rfind(marker)
    if idx != -1:
        return path[idx + len(marker):]
    prefix = "node_modules/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return ""
