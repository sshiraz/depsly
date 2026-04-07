"""Tests for package-level score computation in core.scoring."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.classify import classify_package
from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.scoring import (
    compute_feasibility_score,
    compute_impact_score,
    compute_package_score,
)


def shared_graph_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["direct@1.0.0", "transitive-parent@1.0.0", "alt-parent@1.0.0"],
            },
            "direct@1.0.0": {
                "name": "direct",
                "version": "1.0.0",
                "dependencies": [],
            },
            "transitive-parent@1.0.0": {
                "name": "transitive-parent",
                "version": "1.0.0",
                "dependencies": ["shared@1.0.0"],
            },
            "alt-parent@1.0.0": {
                "name": "alt-parent",
                "version": "1.0.0",
                "dependencies": ["shared@1.0.0"],
            },
            "shared@1.0.0": {
                "name": "shared",
                "version": "1.0.0",
                "dependencies": [],
            },
        },
    }


DEV_DEPS_LOCKFILE = json.dumps({
    "name": "my-app",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "my-app",
            "version": "1.0.0",
            "dependencies": {"react": "^18.2.0"},
            "devDependencies": {"typescript": "^5.0.0"},
        },
        "node_modules/react": {"version": "18.2.0"},
        "node_modules/typescript": {"version": "5.3.3"},
    },
})


class TestImpactScore:
    def test_missing_package_is_zero(self):
        graph = build_graph(shared_graph_data())
        assert compute_impact_score(graph, "missing@0.0.0") == 0.0

    def test_direct_dependency_has_positive_impact(self):
        graph = build_graph(shared_graph_data())
        impact = compute_impact_score(graph, "direct@1.0.0")
        assert impact == 1 / 5


class TestFeasibilityScore:
    def test_score_stays_in_bounds(self):
        normalized = parse_package_lock(DEV_DEPS_LOCKFILE)
        graph = build_graph(normalized)
        classification = classify_package(graph, "typescript@5.3.3", normalized)
        score = compute_feasibility_score(graph, "typescript@5.3.3", classification)
        assert 0.0 <= score <= 1.0

    def test_direct_dev_tooling_can_match_non_dev_direct(self):
        normalized = parse_package_lock(DEV_DEPS_LOCKFILE)
        graph = build_graph(normalized)
        direct_prod = classify_package(graph, "react@18.2.0", normalized)
        direct_dev = classify_package(graph, "typescript@5.3.3", normalized)
        assert compute_feasibility_score(graph, "typescript@5.3.3", direct_dev) == (
            compute_feasibility_score(graph, "react@18.2.0", direct_prod)
        )

    def test_direct_scores_higher_than_shared_transitive(self):
        graph = build_graph(shared_graph_data())
        direct = classify_package(graph, "direct@1.0.0")
        transitive = classify_package(graph, "shared@1.0.0")
        assert compute_feasibility_score(graph, "direct@1.0.0", direct) > (
            compute_feasibility_score(graph, "shared@1.0.0", transitive)
        )

    def test_tooling_package_gets_soft_penalty(self):
        normalized = parse_package_lock(json.dumps({
            "name": "my-app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "my-app",
                    "version": "1.0.0",
                    "dependencies": {"react": "^18.2.0", "vite": "^8.0.0"},
                },
                "node_modules/react": {"version": "18.2.0"},
                "node_modules/vite": {"version": "8.0.3"},
            },
        }))
        graph = build_graph(normalized)
        vite = classify_package(graph, "vite@8.0.3", normalized)
        react = classify_package(graph, "react@18.2.0", normalized)
        assert compute_feasibility_score(graph, "vite@8.0.3", vite) < (
            compute_feasibility_score(graph, "react@18.2.0", react)
        )


class TestPackageScore:
    def test_package_score_is_impact_times_feasibility(self):
        graph = build_graph(shared_graph_data())
        classification = classify_package(graph, "direct@1.0.0")
        score = compute_package_score(graph, "direct@1.0.0", classification)
        assert score == (
            compute_impact_score(graph, "direct@1.0.0")
            * compute_feasibility_score(graph, "direct@1.0.0", classification)
        )
