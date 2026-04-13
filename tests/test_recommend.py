"""Tests for core.recommend."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.recommend import recommend_packages
import core.recommend as recommend_module
from core.simulate import simulate_remove as simulate_remove_result


def recommendation_graph_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["direct-a@1.0.0", "parent-a@1.0.0", "parent-b@1.0.0"],
            },
            "direct-a@1.0.0": {
                "name": "direct-a",
                "version": "1.0.0",
                "dependencies": ["direct-leaf@1.0.0"],
            },
            "direct-leaf@1.0.0": {
                "name": "direct-leaf",
                "version": "1.0.0",
                "dependencies": [],
            },
            "parent-a@1.0.0": {
                "name": "parent-a",
                "version": "1.0.0",
                "dependencies": ["shared@1.0.0"],
            },
            "parent-b@1.0.0": {
                "name": "parent-b",
                "version": "1.0.0",
                "dependencies": ["shared@1.0.0"],
            },
            "shared@1.0.0": {
                "name": "shared",
                "version": "1.0.0",
                "dependencies": ["leaf@1.0.0"],
            },
            "leaf@1.0.0": {
                "name": "leaf",
                "version": "1.0.0",
                "dependencies": [],
            },
        },
    }


DEV_LOCKFILE = json.dumps({
    "name": "my-app",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "my-app",
            "version": "1.0.0",
            "dependencies": {
                "react": "^18.2.0",
                "eslint": "^9.0.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0"
            }
        },
        "node_modules/react": {"version": "18.2.0"},
        "node_modules/eslint": {"version": "9.39.4"},
        "node_modules/typescript": {"version": "5.3.3"},
    }
})


class TestRecommendPackages:
    def test_ranking_is_deterministic(self):
        graph = build_graph(recommendation_graph_data())
        r1 = recommend_packages(graph)
        r2 = recommend_packages(graph)
        assert [(r.package_key, r.final_score) for r in r1] == [
            (r.package_key, r.final_score) for r in r2
        ]

    def test_direct_high_impact_ranks_above_shared_transitive(self):
        graph = build_graph(recommendation_graph_data())
        recommendations = recommend_packages(graph)
        assert recommendations[0].package_key == "direct-a@1.0.0"
        shared = next(r for r in recommendations if r.package_key == "shared@1.0.0")
        assert recommendations[0].final_score > shared.final_score

    def test_empty_graph_handled(self):
        graph = build_graph({"root": "missing@1.0.0", "packages": {}})
        assert recommend_packages(graph) == []

    def test_limit_respected(self):
        graph = build_graph(recommendation_graph_data())
        recommendations = recommend_packages(graph, limit=2)
        assert len(recommendations) == 2

    def test_recommendation_types_are_believable(self):
        normalized = parse_package_lock(DEV_LOCKFILE)
        graph = build_graph(normalized)
        recommendations = recommend_packages(graph, normalized_data=normalized)
        by_key = {r.package_key: r for r in recommendations}
        assert by_key["react@18.2.0"].recommendation_type == "REVIEW"
        assert by_key["eslint@9.39.4"].recommendation_type == "REVIEW"
        assert by_key["typescript@5.3.3"].recommendation_type == "REVIEW"

    def test_remove_is_reserved_for_high_confidence_dev_direct_dependencies(self):
        graph = build_graph(
            {
                "root": "app@1.0.0",
                "packages": {
                    "app@1.0.0": {
                        "name": "app",
                        "version": "1.0.0",
                        "dependencies": ["unused-helper@1.0.0"],
                    },
                    "unused-helper@1.0.0": {
                        "name": "unused-helper",
                        "version": "1.0.0",
                        "dependencies": ["leaf-a@1.0.0", "leaf-b@1.0.0"],
                    },
                    "leaf-a@1.0.0": {"name": "leaf-a", "version": "1.0.0", "dependencies": []},
                    "leaf-b@1.0.0": {"name": "leaf-b", "version": "1.0.0", "dependencies": []},
                },
            }
        )
        normalized = {
            "root": "app@1.0.0",
            "root_dev_dependency_keys": ("unused-helper@1.0.0",),
            "packages": {
                "app@1.0.0": {"name": "app", "version": "1.0.0", "dependencies": ["unused-helper@1.0.0"]},
                "unused-helper@1.0.0": {
                    "name": "unused-helper",
                    "version": "1.0.0",
                    "dependencies": ["leaf-a@1.0.0", "leaf-b@1.0.0"],
                },
                "leaf-a@1.0.0": {"name": "leaf-a", "version": "1.0.0", "dependencies": []},
                "leaf-b@1.0.0": {"name": "leaf-b", "version": "1.0.0", "dependencies": []},
            },
        }

        recommendations = recommend_packages(graph, normalized_data=normalized)
        by_key = {r.package_key: r for r in recommendations}
        assert by_key["unused-helper@1.0.0"].recommendation_type == "REMOVE"

    def test_actionability_is_discretized(self):
        normalized = parse_package_lock(DEV_LOCKFILE)
        graph = build_graph(normalized)
        recommendations = recommend_packages(graph, normalized_data=normalized)
        labels = {r.package_key: r.actionability for r in recommendations}
        assert labels["react@18.2.0"] == "HIGH"
        assert labels["eslint@9.39.4"] == "MEDIUM"

    def test_reason_confidence_reflects_direct_vs_transitive(self):
        graph = build_graph(recommendation_graph_data())
        recommendations = recommend_packages(graph)
        by_key = {r.package_key: r for r in recommendations}
        assert by_key["direct-a@1.0.0"].reason_confidence == "HIGH"
        assert by_key["shared@1.0.0"].reason_confidence == "MEDIUM"

    def test_limit_negative_raises(self):
        graph = build_graph(recommendation_graph_data())
        with pytest.raises(ValueError, match="limit must be >= 0"):
            recommend_packages(graph, limit=-1)

    def test_recommendations_simulate_each_package_once(self, monkeypatch):
        graph = build_graph(recommendation_graph_data())
        calls: list[str] = []

        def counting_simulate(graph_obj, package_key):
            calls.append(package_key)
            return simulate_remove_result(graph_obj, package_key)

        monkeypatch.setattr(recommend_module, "simulate_remove", counting_simulate)

        recommendations = recommend_packages(graph)

        expected = sorted(
            key for key in graph.nodes
            if key != graph.root_key
        )
        assert sorted(calls) == expected
        assert len(calls) == len(expected)
        assert recommendations
