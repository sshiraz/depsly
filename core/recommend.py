"""Deterministic recommendation engine for package actions."""

from __future__ import annotations

from core.classify import classify_all_packages
from core.graph import DependencyGraph, traverse_bfs
from core.models import Recommendation
from core.scoring import compute_feasibility_score, compute_package_score, looks_like_tooling_package
from core.simulate import simulate_remove


def recommend_packages(
    graph: DependencyGraph,
    normalized_data: dict | None = None,
    limit: int = 10,
) -> list[Recommendation]:
    """Rank reachable non-root packages by structural impact and feasibility."""
    if limit < 0:
        raise ValueError(f"limit must be >= 0, got {limit}")
    if limit == 0 or graph.root is None:
        return []

    classifications = classify_all_packages(graph, normalized_data=normalized_data)
    before_keys = set(traverse_bfs(graph))
    recommendations: list[Recommendation] = []

    for package_key in sorted(graph.nodes):
        classification = classifications[package_key]
        if classification.is_root or classification.depth_from_root is None:
            continue

        simulation = simulate_remove(graph, package_key, before_keys=before_keys)
        impact_score = simulation.percent_removed
        feasibility_score = compute_feasibility_score(graph, package_key, classification)
        final_score = compute_package_score(
            graph,
            package_key,
            classification,
            impact_score=impact_score,
            feasibility_score=feasibility_score,
        )
        recommendation_type = _recommendation_type(
            package_key,
            classification.is_direct_dependency,
            classification.is_dev_dependency,
            impact_score,
            feasibility_score,
        )
        rationale = _rationale(
            package_key,
            classification.is_direct_dependency,
            classification.is_transitive_dependency,
            classification.is_dev_dependency,
            impact_score,
            feasibility_score,
            simulation.removed_count,
        )

        recommendations.append(
            Recommendation(
                package_key=package_key,
                recommendation_type=recommendation_type,
                actionability=_actionability_label(feasibility_score),
                reason_confidence=_reason_confidence(classification),
                impact_score=impact_score,
                feasibility_score=feasibility_score,
                final_score=final_score,
                rationale=rationale,
                classification=classification,
            )
        )

    recommendations.sort(key=lambda rec: (-rec.final_score, rec.package_key))
    return recommendations[:limit]


def _recommendation_type(
    package_key: str,
    is_direct: bool,
    is_dev: bool | None,
    impact_score: float,
    feasibility_score: float,
) -> str:
    """Classify the recommended action type."""
    if (
        is_direct
        and is_dev is True
        and impact_score >= 0.15
        and feasibility_score >= 0.7
        and not looks_like_tooling_package(package_key)
    ):
        return "REMOVE"
    if not is_direct and impact_score >= 0.15 and feasibility_score < 0.6:
        return "TRACE_UPSTREAM"
    if impact_score >= 0.2:
        return "REVIEW"
    if impact_score >= 0.05 and is_direct:
        return "REVIEW"
    return "DEFER"


def _actionability_label(feasibility_score: float) -> str:
    """Discretize internal feasibility for human-facing display."""
    if feasibility_score >= 0.8:
        return "HIGH"
    if feasibility_score >= 0.5:
        return "MEDIUM"
    return "LOW"


def _reason_confidence(classification) -> str:
    """Estimate confidence in the recommendation rationale from available facts."""
    has_core_facts = (
        classification.depth_from_root is not None
        and classification.parent_count >= 0
    )
    if not has_core_facts:
        return "LOW"
    if classification.is_direct_dependency and classification.is_dev_dependency is not None:
        return "HIGH"
    return "MEDIUM"


def _rationale(
    package_key: str,
    is_direct: bool,
    is_transitive: bool,
    is_dev: bool | None,
    impact_score: float,
    feasibility_score: float,
    removed_count: int,
) -> tuple[str, ...]:
    """Build short deterministic rationale bullets."""
    reasons: list[str] = []

    if is_direct:
        reasons.append("Direct dependency")
    elif is_transitive:
        reasons.append("Transitive dependency")

    if is_dev is True:
        reasons.append("Development-only package")
    elif is_direct:
        reasons.append("Application dependency")

    if impact_score >= 0.3:
        reasons.append(f"High structural impact ({removed_count} packages)")
    elif impact_score >= 0.1:
        reasons.append(f"Moderate structural impact ({removed_count} packages)")
    else:
        reasons.append(f"Low structural impact ({removed_count} packages)")

    if feasibility_score >= 0.75:
        reasons.append("High actionability")
    elif feasibility_score >= 0.5:
        reasons.append("Moderate actionability")
    else:
        reasons.append("Low actionability")

    if looks_like_tooling_package(package_key):
        reasons.append("Likely build or tooling dependency")

    return tuple(reasons[:3])
