"""Parse supported JS lockfiles into the normalized format expected by build_graph()."""

from __future__ import annotations

import json
from pathlib import Path


class IngestionError(Exception):
    """Raised when a lockfile cannot be parsed."""


def parse_lockfile(
    lockfile: str | Path,
    *,
    include_dev: bool = True,
) -> dict:
    """Parse a supported lockfile and return normalized graph input."""
    path = _coerce_path(lockfile)
    if path is None:
        text = _coerce_text(lockfile)
        if text.lstrip().startswith("{"):
            return parse_package_lock(text, include_dev=include_dev)
        raise IngestionError(
            "String lockfile contents are only supported for package-lock.json. "
            "Pass a yarn.lock path to parse Yarn lockfiles."
        )

    filename = path.name
    if filename == "package-lock.json":
        return parse_package_lock(path, include_dev=include_dev)
    if filename == "yarn.lock":
        return parse_yarn_lock(path, include_dev=include_dev)
    if path.suffix == ".json":
        return parse_package_lock(path, include_dev=include_dev)

    raise IngestionError(
        f"Unsupported lockfile '{filename}'. Expected package-lock.json, yarn.lock, or a JSON package-lock file."
    )


def parse_package_lock(
    lockfile: str | Path,
    *,
    include_dev: bool = True,
) -> dict:
    """Parse a package-lock.json file and return normalized graph input.

    Supports lockfileVersion 2 and 3 (npm v7+). The returned dict is ready
    to pass directly to build_graph().
    """
    path = _coerce_path(lockfile)
    if path is not None:
        raw = json.loads(path.read_text())
    else:
        raw = json.loads(_coerce_text(lockfile))

    lockfile_version = raw.get("lockfileVersion")
    if lockfile_version not in (2, 3):
        raise IngestionError(
            f"Unsupported lockfileVersion: {lockfile_version}. Expected 2 or 3."
        )

    packages = raw.get("packages", {})
    if not isinstance(packages, dict):
        raise IngestionError("'packages' field must be a dict")

    return _normalize_package_lock(packages, include_dev=include_dev)


def parse_yarn_lock(
    lockfile: Path,
    *,
    include_dev: bool = True,
) -> dict:
    """Parse a Yarn Classic v1 yarn.lock file and return normalized graph input."""
    if lockfile.name != "yarn.lock":
        raise IngestionError("Yarn lockfile path must end with yarn.lock")

    lines = lockfile.read_text(encoding="utf-8").splitlines()
    if not any("yarn lockfile v1" in line for line in lines[:5]):
        raise IngestionError("Unsupported yarn.lock format. Expected Yarn Classic v1.")

    entries = _parse_yarn_v1_entries(lines)
    if not entries:
        raise IngestionError("yarn.lock did not contain any package entries.")

    selector_to_key: dict[str, str] = {}
    packages: dict[str, dict] = {}

    for entry in entries:
        name = _selector_name(entry["selectors"][0])
        version = entry.get("version")
        if not version:
            raise IngestionError(f"Missing version for yarn entry: {entry['selectors'][0]}")
        key = f"{name}@{version}"
        packages.setdefault(
            key,
            {
                "name": name,
                "version": version,
                "dependencies": [],
                "selectors": [],
            },
        )
        packages[key]["selectors"].extend(entry["selectors"])
        for selector in entry["selectors"]:
            selector_to_key[selector] = key

    manifest = _read_sibling_package_json(lockfile)
    root_name = manifest.get("name") or lockfile.parent.name or "yarn-project"
    root_version = manifest.get("version") or "0.0.0"
    root_dependencies = _root_dependency_requests(manifest, include_dev=include_dev)

    for entry in entries:
        key = selector_to_key[entry["selectors"][0]]
        normalized_deps: list[str] = []
        for dep_name, dep_range in entry.get("dependencies", {}).items():
            dep_key = _resolve_yarn_dependency(dep_name, dep_range, selector_to_key, packages)
            if dep_key is not None and dep_key not in normalized_deps:
                normalized_deps.append(dep_key)
        packages[key]["dependencies"] = normalized_deps

    if root_dependencies:
        root_dep_keys = []
        unresolved = []
        for dep_name, dep_range in root_dependencies.items():
            dep_key = _resolve_yarn_dependency(dep_name, dep_range, selector_to_key, packages)
            if dep_key is None:
                unresolved.append(dep_name)
                continue
            if dep_key not in root_dep_keys:
                root_dep_keys.append(dep_key)
    else:
        root_dep_keys = _yarn_root_fallback(packages)
        unresolved = []

    root_key = f"{root_name}@{root_version}"
    root_entry = {
        "name": root_name,
        "version": root_version,
        "dependencies": root_dep_keys,
    }
    if unresolved:
        root_entry["unresolved_dependencies"] = sorted(set(unresolved))

    root_dev_keys: list[str] = []
    if include_dev and manifest:
        for dep_name, dep_range in manifest.get("devDependencies", {}).items():
            dep_key = _resolve_yarn_dependency(dep_name, dep_range, selector_to_key, packages)
            if dep_key is not None:
                root_dev_keys.append(dep_key)

    normalized_packages = {
        root_key: root_entry,
    }
    for key, package in packages.items():
        normalized_packages[key] = {
            "name": package["name"],
            "version": package["version"],
            "dependencies": package["dependencies"],
        }

    return {
        "root": root_key,
        "packages": normalized_packages,
        "root_dev_dependency_keys": tuple(sorted(set(root_dev_keys))),
    }


def _normalize_package_lock(packages: dict, *, include_dev: bool) -> dict:
    if "" not in packages:
        raise IngestionError("Lockfile has no root entry (empty string key in packages)")

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


def _parse_yarn_v1_entries(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    in_dependencies = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue

        if not raw_line.startswith(" "):
            if not line.endswith(":"):
                raise IngestionError(f"Invalid yarn.lock entry header: {line}")
            selectors = _parse_yarn_selectors(line[:-1])
            current = {"selectors": selectors, "dependencies": {}}
            entries.append(current)
            in_dependencies = False
            continue

        if current is None:
            continue

        if raw_line.startswith("  ") and not raw_line.startswith("    "):
            stripped = line.strip()
            if stripped == "dependencies:":
                in_dependencies = True
                continue

            in_dependencies = False
            key, value = _parse_yarn_property(stripped)
            current[key] = value
            continue

        if in_dependencies and raw_line.startswith("    "):
            dep_name, dep_range = _parse_yarn_dependency(line.strip())
            current["dependencies"][dep_name] = dep_range
            continue

    return entries


def _parse_yarn_selectors(raw: str) -> list[str]:
    selectors: list[str] = []
    current: list[str] = []
    in_quotes = False

    for char in raw:
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
            continue
        if char == "," and not in_quotes:
            selectors.append(_strip_quotes("".join(current).strip()))
            current = []
            continue
        current.append(char)

    tail = "".join(current).strip()
    if tail:
        selectors.append(_strip_quotes(tail))
    return selectors


def _parse_yarn_property(line: str) -> tuple[str, str]:
    key, _, raw_value = line.partition(" ")
    return key, _strip_quotes(raw_value.strip())


def _parse_yarn_dependency(line: str) -> tuple[str, str]:
    if line.startswith('"'):
        end = line.find('"', 1)
        if end == -1:
            raise IngestionError(f"Invalid yarn dependency line: {line}")
        dep_name = line[1:end]
        dep_range = _strip_quotes(line[end + 1 :].strip())
        return dep_name, dep_range

    dep_name, _, raw_range = line.partition(" ")
    return dep_name, _strip_quotes(raw_range.strip())


def _read_sibling_package_json(lockfile: Path) -> dict:
    manifest_path = lockfile.with_name("package.json")
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IngestionError(f"Invalid sibling package.json near {lockfile}") from exc


def _root_dependency_requests(manifest: dict, *, include_dev: bool) -> dict[str, str]:
    dependencies = dict(manifest.get("dependencies", {}))
    if include_dev:
        dependencies.update(manifest.get("devDependencies", {}))
    return dependencies


def _resolve_yarn_dependency(
    dep_name: str,
    dep_range: str,
    selector_to_key: dict[str, str],
    packages: dict[str, dict],
) -> str | None:
    candidates = [
        f"{dep_name}@{dep_range}",
        f"{dep_name}@npm:{dep_range}",
        dep_name,
    ]
    for candidate in candidates:
        dep_key = selector_to_key.get(candidate)
        if dep_key is not None:
            return dep_key

    matching_keys: list[str] = []
    for selector, dep_key in selector_to_key.items():
        if _selector_name(selector) == dep_name:
            matching_keys.append(dep_key)

    if not matching_keys:
        return None

    preferred = sorted(
        set(matching_keys),
        key=lambda key: (0 if packages[key]["version"] == dep_range else 1, key),
    )
    return preferred[0]


def _yarn_root_fallback(packages: dict[str, dict]) -> list[str]:
    depended_on: set[str] = set()
    for package in packages.values():
        depended_on.update(package["dependencies"])
    return sorted(key for key in packages if key not in depended_on)


def _selector_name(selector: str) -> str:
    if selector.startswith("@"):
        second_at = selector.find("@", 1)
        if second_at == -1:
            return selector
        return selector[:second_at]
    first_at = selector.find("@")
    if first_at == -1:
        return selector
    return selector[:first_at]


def _resolve_dep_path(
    dependent_path: str,
    dep_name: str,
    packages: dict,
) -> str | None:
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
    marker = "/node_modules/"
    idx = path.rfind(marker)
    if idx != -1:
        return path[idx + len(marker):]
    prefix = "node_modules/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return ""


def _coerce_path(lockfile: str | Path) -> Path | None:
    if isinstance(lockfile, Path):
        if not lockfile.exists():
            raise IngestionError(f"File not found: {lockfile}")
        return lockfile

    if isinstance(lockfile, str) and not lockfile.lstrip().startswith("{"):
        candidate = Path(lockfile)
        if candidate.exists():
            return candidate
    return None


def _coerce_text(lockfile: str | Path) -> str:
    if isinstance(lockfile, Path):
        return lockfile.read_text(encoding="utf-8")
    return str(lockfile)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value
