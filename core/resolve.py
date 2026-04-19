"""Helpers for resolving package identifiers into canonical package keys."""

from __future__ import annotations

from core.classify import classify_all_packages
from core.graph import DependencyGraph, traverse_bfs
from core.simulate import simulate_remove


def resolve_package_key(graph: DependencyGraph, package_ref: str, normalized_data: dict | None = None) -> str | None:
    """Resolve a user-facing package reference to a canonical package key.

    Resolution rules:
    - exact key match wins immediately
    - bare package name resolves deterministically
    - if multiple installed versions exist:
      1. prefer direct dependency
      2. then higher structural impact
      3. then lexical key order
    """
    if package_ref in graph.nodes:
        return package_ref

    matches = sorted(key for key, node in graph.nodes.items() if node.name == package_ref)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    classifications = classify_all_packages(graph, normalized_data=normalized_data)
    impact_cache: dict[str, float] = {}
    before_keys = set(traverse_bfs(graph))

    def sort_key(package_key: str) -> tuple[int, float, str]:
        classification = classifications[package_key]
        impact = impact_cache.setdefault(
            package_key,
            simulate_remove(graph, package_key, before_keys=before_keys).percent_removed,
        )
        return (
            0 if classification.is_direct_dependency else 1,
            -impact,
            package_key,
        )

    return sorted(matches, key=sort_key)[0]
