"""Structural analysis of a dependency graph.

Accepts a DependencyGraph and produces deterministic, graph-derived metrics.
No external API calls, no LLM logic — pure graph analysis.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.graph import (
    DependencyGraph,
    collect_transitive_deps,
    graph_stats,
)
from core.simulate import simulate_remove


@dataclass
class GraphReport:
    """Structural analysis report for a dependency graph."""

    root_package_key: str | None
    total_nodes: int
    total_edges: int
    max_depth: int
    has_cycle: bool
    direct_dependency_count: int
    transitive_dependency_count: int
    unresolved_dependency_count: int
    leaf_package_count: int
    top_packages_by_fanout: list[tuple[str, int]]
    top_packages_by_blast_radius: list[tuple[str, int, float]]


def compute_blast_radius(
    graph: DependencyGraph,
    package_key: str,
    *,
    include_self: bool = False,
) -> tuple[int, float]:
    """Compute how many nodes depend on a package, directly or indirectly.

    Traverses upward through dependents. Cycle-safe.

    Returns:
        (affected_count, affected_fraction) where fraction is in [0.0, 1.0].
        Returns (0, 0.0) if package_key does not exist.
    """
    node = graph.get(package_key)
    if node is None:
        return (0, 0.0)

    visited: set[str] = set()
    stack = list(node.dependents)

    while stack:
        current = stack.pop()
        if current.key in visited:
            continue
        visited.add(current.key)
        for dep in current.dependents:
            if dep.key not in visited:
                stack.append(dep)

    if include_self:
        visited.add(package_key)
    else:
        visited.discard(package_key)

    total = len(graph.nodes)
    count = len(visited)
    fraction = count / total if total > 0 else 0.0
    return (count, fraction)


def top_packages_by_blast_radius(
    graph: DependencyGraph,
    *,
    limit: int = 10,
    exclude_root: bool = True,
) -> list[tuple[str, int, float]]:
    """Rank packages by blast radius (descending).

    Returns list of (package_key, affected_count, affected_fraction).
    Sort: affected_count desc, then key asc for stable ties.
    """
    if limit < 0:
        raise ValueError(f"limit must be >= 0, got {limit}")
    if limit == 0:
        return []

    results: list[tuple[str, int, float]] = []
    for key in graph.nodes:
        if exclude_root and key == graph.root_key:
            continue
        count, fraction = compute_blast_radius(graph, key)
        results.append((key, count, fraction))

    results.sort(key=lambda x: (-x[1], x[0]))
    return results[:limit]


def analyze_graph(graph: DependencyGraph, *, fanout_limit: int = 10) -> GraphReport:
    """Produce a structural analysis report for the given graph.

    Args:
        graph: A built DependencyGraph.
        fanout_limit: Max number of entries in top_packages_by_fanout.
            Must be >= 0. Zero returns an empty list.

    Returns:
        GraphReport with all computed metrics.
    """
    if fanout_limit < 0:
        raise ValueError(f"fanout_limit must be >= 0, got {fanout_limit}")

    stats = graph_stats(graph)

    root = graph.root
    if root is not None:
        direct = len(root.dependencies)
        transitive = len(collect_transitive_deps(graph))
    else:
        direct = 0
        transitive = 0

    unresolved = len(graph.missing_keys)

    leaf_count = sum(
        1 for node in graph.nodes.values() if len(node.dependencies) == 0
    )

    # Fan-out: number of direct dependencies per node
    # Sort by (-count, key) for deterministic ordering on ties
    fanout = sorted(
        [(node.key, len(node.dependencies)) for node in graph.nodes.values()],
        key=lambda x: (-x[1], x[0]),
    )[:fanout_limit]

    blast = top_packages_by_blast_radius(graph, limit=fanout_limit)

    return GraphReport(
        root_package_key=graph.root_key,
        total_nodes=stats["total_nodes"],
        total_edges=stats["total_edges"],
        max_depth=stats["max_depth"],
        has_cycle=stats["has_cycle"],
        direct_dependency_count=direct,
        transitive_dependency_count=transitive,
        unresolved_dependency_count=unresolved,
        leaf_package_count=leaf_count,
        top_packages_by_fanout=fanout,
        top_packages_by_blast_radius=blast,
    )


@dataclass
class RemovalSimulationReport:
    """Result of simulating the removal of a package from the graph."""

    package_key: str
    package_found: bool
    affected_node_count: int
    removed_subgraph_node_count: int
    before_report: GraphReport
    after_report: GraphReport
    risk_delta: int | None
    top_impacted_packages: list[tuple[str, int]]


def analyze_removal_impact(
    graph: DependencyGraph,
    package_key: str,
    *,
    before_report: GraphReport | None = None,
    simulation=None,
) -> RemovalSimulationReport:
    """Simulate removing a package and compare before/after metrics.

    Computes full GraphReport for both the original and simulated graph,
    then derives impact metrics from the difference.
    """
    before = before_report if before_report is not None else analyze_graph(graph)
    simulation_result = simulation if simulation is not None else simulate_remove(graph, package_key)
    after = analyze_graph(simulation_result.simulated_graph)

    return RemovalSimulationReport(
        package_key=package_key,
        package_found=simulation_result.package_found,
        affected_node_count=simulation_result.removed_count,
        removed_subgraph_node_count=simulation_result.removed_count,
        before_report=before,
        after_report=after,
        risk_delta=None,
        top_impacted_packages=list(simulation_result.impacted_packages),
    )
