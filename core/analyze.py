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
    )
