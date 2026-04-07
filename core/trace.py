"""Deterministic root-to-package tracing."""

from __future__ import annotations

from core.graph import DependencyGraph, shortest_depths_from_root
from core.models import TraceResult


def trace_package(
    graph: DependencyGraph,
    package_key: str,
    max_paths: int = 3,
) -> TraceResult:
    """Return up to max_paths shortest root-to-target paths.

    Paths are deterministic:
    - only shortest paths are considered
    - child traversal is ordered lexicographically by package key
    - returned paths are immutable tuples
    """
    if max_paths < 0:
        raise ValueError(f"max_paths must be >= 0, got {max_paths}")

    package_found = package_key in graph.nodes
    depths = shortest_depths_from_root(graph)
    reachable = package_key in depths

    if not package_found or not reachable or graph.root_key is None:
        return TraceResult(
            package_key=package_key,
            package_found=package_found,
            reachable_from_root=reachable,
            paths=(),
        )

    if max_paths == 0:
        return TraceResult(
            package_key=package_key,
            package_found=True,
            reachable_from_root=True,
            paths=(),
        )

    target_depth = depths[package_key]
    target = graph.nodes[package_key]
    root = graph.root
    if root is None:
        return TraceResult(
            package_key=package_key,
            package_found=True,
            reachable_from_root=True,
            paths=(),
        )

    paths: list[tuple[str, ...]] = []

    def _walk(node_key: str, path: tuple[str, ...]) -> None:
        if len(paths) >= max_paths:
            return
        if node_key == package_key:
            paths.append(path)
            return

        node = graph.nodes[node_key]
        current_depth = depths[node_key]
        for dep in sorted(node.dependencies, key=lambda child: child.key):
            dep_depth = depths.get(dep.key)
            if dep_depth is None:
                continue
            if dep_depth != current_depth + 1:
                continue
            if dep_depth > target_depth:
                continue
            if dep.key in path:
                continue
            _walk(dep.key, path + (dep.key,))

    _walk(root.key, (root.key,))
    return TraceResult(
        package_key=target.key,
        package_found=True,
        reachable_from_root=True,
        paths=tuple(paths),
    )
