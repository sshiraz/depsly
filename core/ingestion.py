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
    if filename == "pnpm-lock.yaml":
        return parse_pnpm_lock(path, include_dev=include_dev)
    if path.suffix == ".json":
        return parse_package_lock(path, include_dev=include_dev)

    raise IngestionError(
        f"Unsupported lockfile '{filename}'. Expected package-lock.json, yarn.lock, pnpm-lock.yaml, or a JSON package-lock file."
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


def parse_pnpm_lock(
    lockfile: Path,
    *,
    include_dev: bool = True,
) -> dict:
    """Parse a pnpm-lock.yaml file and return normalized graph input."""
    if lockfile.name != "pnpm-lock.yaml":
        raise IngestionError("pnpm lockfile path must end with pnpm-lock.yaml")

    raw = _read_yaml_file(lockfile)
    if not isinstance(raw, dict):
        raise IngestionError("pnpm-lock.yaml must decode to a mapping")

    importers = raw.get("importers", {})
    if not isinstance(importers, dict) or "." not in importers:
        raise IngestionError("pnpm-lock.yaml must contain an importers section with a root importer '.'")

    package_entries = raw.get("packages", {})
    snapshot_entries = raw.get("snapshots", {})
    if not isinstance(package_entries, dict):
        raise IngestionError("'packages' section in pnpm-lock.yaml must be a mapping")
    if not isinstance(snapshot_entries, dict):
        raise IngestionError("'snapshots' section in pnpm-lock.yaml must be a mapping")

    importer_keys_by_path: dict[str, str] = {}
    importer_keys_by_name: dict[str, str] = {}
    normalized_packages: dict[str, dict] = {}

    for importer_path, importer_data in importers.items():
        if not isinstance(importer_data, dict):
            continue
        importer_key, importer_name = _pnpm_importer_key(lockfile, importer_path)
        importer_keys_by_path[importer_path] = importer_key
        importer_keys_by_name[importer_name] = importer_key
        normalized_packages.setdefault(
            importer_key,
            {
                "name": importer_name,
                "version": _pnpm_version_component(importer_key),
                "dependencies": [],
                "install_paths": [importer_path],
            },
        )

    package_key_map: dict[str, str] = {}
    all_entry_ids = set(package_entries) | set(snapshot_entries)
    for raw_id in sorted(all_entry_ids):
        canonical_key = _pnpm_canonical_key(raw_id)
        package_key_map[raw_id] = canonical_key
        name = _selector_name(canonical_key)
        version = _pnpm_version_component(canonical_key)
        normalized_packages.setdefault(
            canonical_key,
            {
                "name": name,
                "version": version,
                "dependencies": [],
                "install_paths": [f"pnpm:{raw_id}"],
            },
        )

    root_importer = importers["."]
    root_dep_requests = _pnpm_importer_requests(root_importer, include_dev=include_dev)
    root_dev_requests = _pnpm_importer_requests(root_importer, include_dev=True, include_prod=False)

    for importer_path, importer_data in importers.items():
        if not isinstance(importer_data, dict):
            continue
        importer_key = importer_keys_by_path[importer_path]
        dependency_requests = _pnpm_importer_requests(importer_data, include_dev=include_dev)
        normalized_packages[importer_key]["dependencies"] = _pnpm_resolve_dependency_requests(
            dependency_requests,
            importer_path=importer_path,
            lockfile=lockfile,
            package_key_map=package_key_map,
            importer_keys_by_path=importer_keys_by_path,
            importer_keys_by_name=importer_keys_by_name,
        )

    for raw_id in sorted(all_entry_ids):
        canonical_key = package_key_map[raw_id]
        snapshot_data = snapshot_entries.get(raw_id, {})
        package_data = package_entries.get(raw_id, {})
        if not isinstance(snapshot_data, dict):
            snapshot_data = {}
        if not isinstance(package_data, dict):
            package_data = {}

        dependency_requests: dict[str, str] = {}
        for section in ("dependencies", "optionalDependencies"):
            section_data = snapshot_data.get(section)
            if isinstance(section_data, dict):
                dependency_requests.update({name: str(value) for name, value in section_data.items()})
            elif isinstance(package_data.get(section), dict):
                dependency_requests.update({name: str(value) for name, value in package_data[section].items()})

        normalized_packages[canonical_key]["dependencies"] = _pnpm_resolve_dependency_requests(
            dependency_requests,
            importer_path=None,
            lockfile=lockfile,
            package_key_map=package_key_map,
            importer_keys_by_path=importer_keys_by_path,
            importer_keys_by_name=importer_keys_by_name,
        )

    root_key = importer_keys_by_path["."]
    root_entry = normalized_packages[root_key]
    root_entry["dependencies"] = _pnpm_resolve_dependency_requests(
        root_dep_requests,
        importer_path=".",
        lockfile=lockfile,
        package_key_map=package_key_map,
        importer_keys_by_path=importer_keys_by_path,
        importer_keys_by_name=importer_keys_by_name,
    )

    root_dev_keys = _pnpm_resolve_dependency_requests(
        root_dev_requests,
        importer_path=".",
        lockfile=lockfile,
        package_key_map=package_key_map,
        importer_keys_by_path=importer_keys_by_path,
        importer_keys_by_name=importer_keys_by_name,
    )

    for entry in normalized_packages.values():
        entry["dependencies"] = sorted(dict.fromkeys(entry["dependencies"]))
        entry["install_paths"] = sorted(dict.fromkeys(entry["install_paths"]))

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


def _read_yaml_file(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment issue
        raise IngestionError(
            "PyYAML is required to parse pnpm-lock.yaml files."
        ) from exc

    try:
        decoded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise IngestionError(f"Invalid pnpm-lock.yaml near {path}") from exc

    if decoded is None:
        return {}
    return decoded


def _pnpm_importer_key(lockfile: Path, importer_path: str) -> tuple[str, str]:
    if importer_path == ".":
        manifest_path = lockfile.with_name("package.json")
    else:
        manifest_path = lockfile.parent / importer_path / "package.json"

    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    importer_name = manifest.get("name") or (lockfile.parent.name if importer_path == "." else Path(importer_path).name)
    importer_version = manifest.get("version") or "0.0.0"
    return f"{importer_name}@{importer_version}", importer_name


def _pnpm_importer_requests(
    importer_data: dict,
    *,
    include_dev: bool,
    include_prod: bool = True,
) -> dict[str, str]:
    requests: dict[str, str] = {}
    if include_prod:
        for section in ("dependencies", "optionalDependencies"):
            section_data = importer_data.get(section, {})
            if isinstance(section_data, dict):
                for dep_name, dep_info in section_data.items():
                    resolved = _pnpm_dependency_ref(dep_info)
                    if resolved is not None:
                        requests[dep_name] = resolved
    if include_dev:
        section_data = importer_data.get("devDependencies", {})
        if isinstance(section_data, dict):
            for dep_name, dep_info in section_data.items():
                resolved = _pnpm_dependency_ref(dep_info)
                if resolved is not None:
                    requests[dep_name] = resolved
    return requests


def _pnpm_dependency_ref(dep_info) -> str | None:
    if isinstance(dep_info, str):
        return dep_info
    if isinstance(dep_info, dict):
        version = dep_info.get("version")
        if isinstance(version, str):
            return version
        specifier = dep_info.get("specifier")
        if isinstance(specifier, str):
            return specifier
    return None


def _pnpm_resolve_dependency_requests(
    dependency_requests: dict[str, str],
    *,
    importer_path: str | None,
    lockfile: Path,
    package_key_map: dict[str, str],
    importer_keys_by_path: dict[str, str],
    importer_keys_by_name: dict[str, str],
) -> list[str]:
    resolved: list[str] = []
    for dep_name, dep_ref in dependency_requests.items():
        dep_key = _resolve_pnpm_dependency(
            dep_name,
            dep_ref,
            importer_path=importer_path,
            lockfile=lockfile,
            package_key_map=package_key_map,
            importer_keys_by_path=importer_keys_by_path,
            importer_keys_by_name=importer_keys_by_name,
        )
        if dep_key is not None and dep_key not in resolved:
            resolved.append(dep_key)
    return resolved


def _resolve_pnpm_dependency(
    dep_name: str,
    dep_ref: str,
    *,
    importer_path: str | None,
    lockfile: Path,
    package_key_map: dict[str, str],
    importer_keys_by_path: dict[str, str],
    importer_keys_by_name: dict[str, str],
) -> str | None:
    dep_ref = dep_ref.strip()
    if not dep_ref:
        return None

    if dep_ref.startswith("link:"):
        linked = dep_ref[len("link:") :]
        target_importer = _normalize_linked_importer_path(lockfile, importer_path, linked)
        if target_importer in importer_keys_by_path:
            return importer_keys_by_path[target_importer]
        return importer_keys_by_name.get(dep_name)

    if dep_ref.startswith("workspace:"):
        return importer_keys_by_name.get(dep_name)

    if dep_ref.startswith("npm:"):
        alias_target = dep_ref[len("npm:") :]
        if "@" in alias_target:
            aliased_name, aliased_version = alias_target.rsplit("@", 1)
            candidate_ids = [
                f"{aliased_name}@{aliased_version}",
                f"{dep_name}@{aliased_version}",
            ]
        else:
            candidate_ids = [f"{dep_name}@{alias_target}"]
    else:
        candidate_ids = [f"{dep_name}@{dep_ref}"]

    for candidate in candidate_ids:
        if candidate in package_key_map:
            return package_key_map[candidate]

    matching_ids = [raw_id for raw_id in package_key_map if _selector_name(raw_id) == dep_name]
    if not matching_ids:
        return None

    preferred = sorted(
        matching_ids,
        key=lambda raw_id: (0 if _pnpm_version_component(raw_id) == dep_ref else 1, raw_id),
    )
    return package_key_map[preferred[0]]


def _normalize_linked_importer_path(lockfile: Path, importer_path: str | None, linked: str) -> str:
    root = lockfile.parent.resolve()
    if importer_path in (None, "."):
        base = root
    else:
        base = (root / importer_path).resolve()
    normalized = (base / linked).resolve().as_posix()
    root_normalized = root.as_posix()
    if normalized == root_normalized:
        return "."
    if normalized.startswith(root_normalized + "/"):
        return normalized[len(root_normalized) + 1 :]
    return Path(linked).as_posix()


def _pnpm_canonical_key(raw_id: str) -> str:
    raw_id = raw_id.lstrip("/")
    name = _selector_name(raw_id)
    version = raw_id[len(name) + 1 :]
    return f"{name}@{version}"


def _pnpm_version_component(raw_id: str) -> str:
    raw_id = raw_id.lstrip("/")
    name = _selector_name(raw_id)
    return raw_id[len(name) + 1 :]


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
