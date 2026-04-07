"""Project-level risk scoring from structural graph metrics.

Pure policy module — no I/O, no LLM, no external calls.
All thresholds and point assignments live here.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.analyze import GraphReport


@dataclass
class ScoreComponent:
    """A single scored dimension of project risk."""

    category: str
    points: int
    reason: str


@dataclass
class ProjectScore:
    """Aggregated project risk score with breakdown."""

    total: int
    label: str
    components: list[ScoreComponent]


def _label_for_score(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MODERATE"
    return "LOW"


def score_project(report: GraphReport) -> ProjectScore:
    """Compute a 0-100 risk score with breakdown from a GraphReport.

    Scoring dimensions:
        Depth         (0-25)  — deeper dependency chains = riskier
        Concentration (0-25)  — few packages dominating edges = riskier
        Size          (0-15)  — more total nodes = riskier
        Transitive    (0-25)  — high transitive-to-direct ratio = riskier
        Unresolved    (0-15)  — missing dependencies = riskier
        Cycles        (0-10)  — circular dependencies = riskier
    """
    components: list[ScoreComponent] = []

    # Depth (0-25)
    depth_pts = 0
    if report.max_depth >= 10:
        depth_pts = 25
    elif report.max_depth >= 7:
        depth_pts = 20
    elif report.max_depth >= 5:
        depth_pts = 15
    elif report.max_depth >= 3:
        depth_pts = 8
    components.append(ScoreComponent("Depth risk", depth_pts, f"depth {report.max_depth}"))

    # Concentration (0-25)
    concentration_pts = 0
    if report.total_edges > 0 and report.top_packages_by_fanout:
        top3_edges = sum(c for _, c in report.top_packages_by_fanout[:3])
        concentration = top3_edges / report.total_edges
        if concentration >= 0.5:
            concentration_pts = 25
        elif concentration >= 0.4:
            concentration_pts = 20
        elif concentration >= 0.3:
            concentration_pts = 15
        elif concentration >= 0.15:
            concentration_pts = 8
    components.append(ScoreComponent("Centralization risk", concentration_pts, "top packages dominate"))

    # Size (0-15)
    size_pts = 0
    if report.total_nodes >= 500:
        size_pts = 15
    elif report.total_nodes >= 300:
        size_pts = 12
    elif report.total_nodes >= 200:
        size_pts = 10
    elif report.total_nodes >= 100:
        size_pts = 5
    components.append(ScoreComponent("Size risk", size_pts, f"{report.total_nodes} dependencies"))

    # Transitive ratio (0-25)
    transitive_pts = 0
    if report.direct_dependency_count > 0:
        ratio = report.transitive_dependency_count / report.direct_dependency_count
        if ratio >= 20:
            transitive_pts = 25
        elif ratio >= 12:
            transitive_pts = 20
        elif ratio >= 8:
            transitive_pts = 15
        elif ratio >= 4:
            transitive_pts = 10
    components.append(ScoreComponent("Transitive risk", transitive_pts, f"{report.transitive_dependency_count} indirect deps"))

    # Unresolved dependencies (0-15)
    unresolved_pts = 0
    if report.unresolved_dependency_count >= 5:
        unresolved_pts = 15
    elif report.unresolved_dependency_count >= 2:
        unresolved_pts = 10
    elif report.unresolved_dependency_count >= 1:
        unresolved_pts = 5
    components.append(ScoreComponent("Unresolved dependencies", unresolved_pts, f"{report.unresolved_dependency_count} missing"))

    # Cycles (0-10)
    cycle_pts = 10 if report.has_cycle else 0
    components.append(ScoreComponent("Cycle risk", cycle_pts, "circular dependency" if report.has_cycle else "none"))

    total = min(sum(c.points for c in components), 100)
    return ProjectScore(
        total=total,
        label=_label_for_score(total),
        components=components,
    )
