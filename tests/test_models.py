"""Smoke tests for shared model definitions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import DependencyGraph
from core.models import (
    PackageClassification,
    Recommendation,
    RemoveSimulationResult,
    TraceResult,
)


def test_shared_models_import_and_construct():
    classification = PackageClassification(
        package_key="react@18.2.0",
        is_root=False,
        is_direct_dependency=True,
        is_transitive_dependency=False,
        is_dev_dependency=None,
        parent_count=1,
        depth_from_root=1,
    )

    trace = TraceResult(
        package_key="react@18.2.0",
        package_found=True,
        reachable_from_root=True,
        paths=(("app@1.0.0", "react@18.2.0"),),
    )

    simulation = RemoveSimulationResult(
        package_key="react@18.2.0",
        package_found=True,
        removed_keys=("react@18.2.0",),
        removed_count=1,
        total_nodes_before=3,
        total_nodes_after=2,
        percent_removed=1 / 3,
        impacted_packages=(("app@1.0.0", 1),),
        disclaimer="Structural simulation only.",
        simulated_graph=DependencyGraph(),
    )

    recommendation = Recommendation(
        package_key="react@18.2.0",
        recommendation_type="REVIEW",
        impact_score=0.5,
        feasibility_score=0.75,
        final_score=0.375,
        rationale=("Direct dependency", "Moderate blast radius"),
        classification=classification,
    )

    assert trace.paths[0][-1] == "react@18.2.0"
    assert simulation.removed_count == 1
    assert recommendation.classification.is_direct_dependency is True
