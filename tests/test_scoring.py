"""Tests for core.scoring — project risk scoring."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from core.analyze import analyze_graph
from core.scoring import score_project, ProjectScore, ScoreComponent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def simple_graph_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["react@18.2.0"],
            },
            "react@18.2.0": {
                "name": "react",
                "version": "18.2.0",
                "dependencies": [],
            },
        },
    }


def deep_graph_data():
    """a -> b -> c -> d -> e -> f (depth 5)."""
    return {
        "root": "a@1.0.0",
        "packages": {
            "a@1.0.0": {"name": "a", "version": "1.0.0", "dependencies": ["b@1.0.0"]},
            "b@1.0.0": {"name": "b", "version": "1.0.0", "dependencies": ["c@1.0.0"]},
            "c@1.0.0": {"name": "c", "version": "1.0.0", "dependencies": ["d@1.0.0"]},
            "d@1.0.0": {"name": "d", "version": "1.0.0", "dependencies": ["e@1.0.0"]},
            "e@1.0.0": {"name": "e", "version": "1.0.0", "dependencies": ["f@1.0.0"]},
            "f@1.0.0": {"name": "f", "version": "1.0.0", "dependencies": []},
        },
    }


def missing_dep_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["ghost@0.0.1"],
            },
        },
    }


def cycle_data():
    return {
        "root": "a@1.0.0",
        "packages": {
            "a@1.0.0": {"name": "a", "version": "1.0.0", "dependencies": ["b@1.0.0"]},
            "b@1.0.0": {"name": "b", "version": "1.0.0", "dependencies": ["a@1.0.0"]},
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoreProject:
    def test_returns_project_score(self):
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        assert isinstance(result, ProjectScore)
        assert isinstance(result.total, int)
        assert isinstance(result.label, str)
        assert all(isinstance(c, ScoreComponent) for c in result.components)

    def test_score_range(self):
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        assert 0 <= result.total <= 100

    def test_label_simple_graph(self):
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        # Small graph but high concentration (1 edge, top3 = 100%)
        assert result.label == "MODERATE"

    def test_label_thresholds(self):
        """Labels match expected score ranges."""
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        if result.total >= 75:
            assert result.label == "CRITICAL"
        elif result.total >= 50:
            assert result.label == "HIGH"
        elif result.total >= 25:
            assert result.label == "MODERATE"
        else:
            assert result.label == "LOW"

    def test_depth_contributes(self):
        report = analyze_graph(build_graph(deep_graph_data()))
        result = score_project(report)
        depth_comp = next(c for c in result.components if c.category == "Depth risk")
        assert depth_comp.points == 15  # depth 5

    def test_unresolved_contributes(self):
        report = analyze_graph(build_graph(missing_dep_data()))
        result = score_project(report)
        unresolved_comp = next(c for c in result.components if c.category == "Unresolved dependencies")
        assert unresolved_comp.points == 5  # 1 missing

    def test_cycle_contributes(self):
        report = analyze_graph(build_graph(cycle_data()))
        result = score_project(report)
        cycle_comp = next(c for c in result.components if c.category == "Cycle risk")
        assert cycle_comp.points == 10

    def test_no_cycle_zero_points(self):
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        cycle_comp = next(c for c in result.components if c.category == "Cycle risk")
        assert cycle_comp.points == 0

    def test_components_have_reasons(self):
        report = analyze_graph(build_graph(simple_graph_data()))
        result = score_project(report)
        for comp in result.components:
            assert comp.reason  # non-empty

    def test_total_is_sum_of_components(self):
        report = analyze_graph(build_graph(deep_graph_data()))
        result = score_project(report)
        assert result.total == min(sum(c.points for c in result.components), 100)

    def test_deterministic(self):
        report = analyze_graph(build_graph(deep_graph_data()))
        r1 = score_project(report)
        r2 = score_project(report)
        assert r1.total == r2.total
        assert r1.label == r2.label
        assert len(r1.components) == len(r2.components)
        for c1, c2 in zip(r1.components, r2.components):
            assert c1.category == c2.category
            assert c1.points == c2.points
