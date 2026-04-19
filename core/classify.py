"""Deterministic package classification built from graph facts."""

from __future__ import annotations

from core.graph import DependencyGraph, parent_counts, shortest_depths_from_root
from core.models import PackageClassification


def classify_package(
    graph: DependencyGraph,
    package_key: str,
    normalized_data: dict | None = None,
) -> PackageClassification:
    """Classify a package using graph structure and optional ingestion metadata."""
    counts = parent_counts(graph)
    depths = shortest_depths_from_root(graph)
    root = graph.root
    direct_keys = {dep.key for dep in root.dependencies} if root is not None else set()
    dev_keys = set(normalized_data.get("root_dev_dependency_keys", ())) if normalized_data else set()

    return _classify_from_precomputed(
        graph,
        package_key,
        counts=counts,
        depths=depths,
        direct_keys=direct_keys,
        dev_keys=dev_keys,
    )


def _classify_from_precomputed(
    graph: DependencyGraph,
    package_key: str,
    *,
    counts: dict[str, int],
    depths: dict[str, int],
    direct_keys: set[str],
    dev_keys: set[str],
) -> PackageClassification:
    is_root = package_key == graph.root_key and package_key in graph.nodes
    is_direct = package_key in direct_keys
    is_reachable = package_key in depths
    is_transitive = is_reachable and not is_root and not is_direct

    is_dev: bool | None
    if is_root or package_key not in graph.nodes:
        is_dev = False if is_root else None
    else:
        is_dev = package_key in dev_keys

    return PackageClassification(
        package_key=package_key,
        is_root=is_root,
        is_direct_dependency=is_direct,
        is_transitive_dependency=is_transitive,
        is_dev_dependency=is_dev,
        parent_count=counts.get(package_key, 0),
        depth_from_root=depths.get(package_key),
    )


def classify_all_packages(
    graph: DependencyGraph,
    normalized_data: dict | None = None,
) -> dict[str, PackageClassification]:
    """Classify all graph packages with deterministic key ordering."""
    counts = parent_counts(graph)
    depths = shortest_depths_from_root(graph)
    root = graph.root
    direct_keys = {dep.key for dep in root.dependencies} if root is not None else set()
    dev_keys = set(normalized_data.get("root_dev_dependency_keys", ())) if normalized_data else set()

    return {
        key: _classify_from_precomputed(
            graph,
            key,
            counts=counts,
            depths=depths,
            direct_keys=direct_keys,
            dev_keys=dev_keys,
        )
        for key in sorted(graph.nodes)
    }
