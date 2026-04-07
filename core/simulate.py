"""Reusable structural package-removal simulation."""

from __future__ import annotations

from core.graph import DependencyGraph, simulate_remove_package, traverse_bfs
from core.models import RemoveSimulationResult


STRUCTURAL_SIMULATION_DISCLAIMER = (
    "Structural simulation only. Does not guarantee install, build, or runtime correctness."
)


def simulate_remove(graph: DependencyGraph, package_key: str) -> RemoveSimulationResult:
    """Simulate removing a package and return a reusable deterministic result."""
    package_found = package_key in graph.nodes
    simulated_graph = simulate_remove_package(graph, package_key)

    before_keys = set(traverse_bfs(graph))
    after_keys = set(traverse_bfs(simulated_graph))
    removed_keys = tuple(sorted(before_keys - after_keys))
    removed_count = len(removed_keys)

    total_nodes_before = len(graph.nodes)
    total_nodes_after = len(simulated_graph.nodes)
    percent_removed = removed_count / total_nodes_before if total_nodes_before > 0 else 0.0

    impacted_packages: list[tuple[str, int]] = []
    node = graph.get(package_key)
    if node is not None and removed_count > 0:
        for dependent in node.dependents:
            impacted_packages.append((dependent.key, removed_count))
        impacted_packages.sort(key=lambda item: (-item[1], item[0]))
        impacted_packages = impacted_packages[:5]

    return RemoveSimulationResult(
        package_key=package_key,
        package_found=package_found,
        removed_keys=removed_keys,
        removed_count=removed_count,
        total_nodes_before=total_nodes_before,
        total_nodes_after=total_nodes_after,
        percent_removed=percent_removed,
        impacted_packages=tuple(impacted_packages),
        disclaimer=STRUCTURAL_SIMULATION_DISCLAIMER,
        simulated_graph=simulated_graph,
    )
