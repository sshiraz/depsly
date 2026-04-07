"""Shared dataclasses for reusable core workflows.

These are logic-free data containers for simulation, classification,
tracing, and recommendation features that sit above the graph engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.graph import DependencyGraph


@dataclass(frozen=True)
class RemoveSimulationResult:
    """Reusable structural removal simulation result."""

    package_key: str
    package_found: bool
    removed_keys: tuple[str, ...]
    removed_count: int
    total_nodes_before: int
    total_nodes_after: int
    percent_removed: float
    impacted_packages: tuple[tuple[str, int], ...]
    disclaimer: str
    simulated_graph: DependencyGraph = field(repr=False, compare=False)


@dataclass(frozen=True)
class PackageClassification:
    """Canonical package classification facts."""

    package_key: str
    is_root: bool
    is_direct_dependency: bool
    is_transitive_dependency: bool
    is_dev_dependency: bool | None
    parent_count: int
    depth_from_root: int | None


@dataclass(frozen=True)
class TraceResult:
    """Deterministic root-to-target path explanation."""

    package_key: str
    package_found: bool
    reachable_from_root: bool
    paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Recommendation:
    """Ranked action recommendation for a package."""

    package_key: str
    recommendation_type: str
    impact_score: float
    feasibility_score: float
    final_score: float
    rationale: tuple[str, ...]
    classification: PackageClassification
