"""Stable JSON export helpers for CLI scan outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.analyze import GraphReport
from core.models import Recommendation
from core.scoring import PACKAGE_SCORING_VERSION

TOOL_VERSION = "0.1.8"
SCHEMA_VERSION = "1.0"


def scan_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for scan metadata."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def split_package_key(package_key: str) -> tuple[str, str]:
    """Split a package key into (name, version)."""
    name, version = package_key.rsplit("@", 1)
    return name, version


def _classification_scope(recommendation: Recommendation) -> str:
    if recommendation.classification.is_direct_dependency:
        return "direct"
    if recommendation.classification.is_transitive_dependency:
        return "transitive"
    return "unknown"


def export_recommendations(
    *,
    lockfile: Path,
    project_name: str,
    report: GraphReport,
    recommendations: list[Recommendation],
    include_dev: bool,
    limit: int,
) -> dict:
    """Build a stable machine-readable recommendation export."""
    ordered_recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.final_score, recommendation.package_key),
    )

    return {
        "project": {
            "name": project_name,
            "ecosystem": "npm",
            "lockfile": str(lockfile),
            "total_dependencies": report.total_nodes,
            "direct_dependencies": report.direct_dependency_count,
            "transitive_dependencies": report.transitive_dependency_count,
            "max_depth": report.max_depth,
        },
        "recommendations": [
            {
                "package": split_package_key(recommendation.package_key)[0],
                "version": split_package_key(recommendation.package_key)[1],
                "package_key": recommendation.package_key,
                "action": recommendation.recommendation_type,
                "actionability": recommendation.actionability,
                "reason_confidence": recommendation.reason_confidence,
                "impact_score": round(recommendation.impact_score, 6),
                "impact_percent": round(recommendation.impact_score * 100, 2),
                "feasibility_score": round(recommendation.feasibility_score, 6),
                "final_score": round(recommendation.final_score, 6),
                "priority": "HIGH" if recommendation.impact_score >= 0.15 else "NORMAL",
                "classification": {
                    "scope": _classification_scope(recommendation),
                    "is_dev_dependency": recommendation.classification.is_dev_dependency,
                    "parent_count": recommendation.classification.parent_count,
                    "depth_from_root": recommendation.classification.depth_from_root,
                },
                "reasons": list(recommendation.rationale),
            }
            for recommendation in ordered_recommendations
        ],
        "top_blast_radius": [
            {
                "package": split_package_key(package_key)[0],
                "version": split_package_key(package_key)[1],
                "package_key": package_key,
                "affected_count": count,
                "affected_fraction": round(fraction, 6),
            }
            for package_key, count, fraction in report.top_packages_by_blast_radius
        ],
        "scan": {
            "schema_version": SCHEMA_VERSION,
            "timestamp": scan_timestamp(),
            "scoring_version": PACKAGE_SCORING_VERSION,
            "tool_version": TOOL_VERSION,
            "include_dev": include_dev,
            "limit": limit,
        },
    }
