"""Tests for core.analyze — structural graph analysis."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.analyze import (
    analyze_graph,
    analyze_removal_impact,
    compute_blast_radius,
    top_packages_by_blast_radius,
)


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
                "dependencies": ["react@18.2.0", "lodash@4.17.21"],
            },
            "react@18.2.0": {
                "name": "react",
                "version": "18.2.0",
                "dependencies": ["loose-envify@1.4.0"],
            },
            "lodash@4.17.21": {
                "name": "lodash",
                "version": "4.17.21",
                "dependencies": [],
            },
            "loose-envify@1.4.0": {
                "name": "loose-envify",
                "version": "1.4.0",
                "dependencies": [],
            },
        },
    }


def missing_dep_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["react@18.2.0", "ghost@0.0.1"],
            },
            "react@18.2.0": {
                "name": "react",
                "version": "18.2.0",
                "dependencies": [],
            },
        },
    }


def no_root_data():
    return {
        "packages": {
            "a@1.0.0": {
                "name": "a",
                "version": "1.0.0",
                "dependencies": [],
            },
        },
    }


LOCKFILE = json.dumps({
    "name": "my-app",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "my-app",
            "version": "1.0.0",
            "dependencies": {
                "react": "^18.2.0",
                "lodash": "^4.17.21"
            }
        },
        "node_modules/react": {
            "version": "18.2.0",
            "dependencies": {
                "loose-envify": "^1.1.0"
            }
        },
        "node_modules/lodash": {
            "version": "4.17.21"
        },
        "node_modules/loose-envify": {
            "version": "1.4.0",
            "dependencies": {
                "js-tokens": "^3.0.0"
            }
        },
        "node_modules/js-tokens": {
            "version": "4.0.0"
        }
    }
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzeGraph:
    def test_basic_metrics(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        assert report.root_package_key == "app@1.0.0"
        assert report.total_nodes == 4
        assert report.total_edges == 3
        assert report.max_depth == 2
        assert report.has_cycle is False

    def test_direct_dependency_count(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        assert report.direct_dependency_count == 2

    def test_transitive_dependency_count(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        # react, lodash, loose-envify (excludes root)
        assert report.transitive_dependency_count == 3

    def test_unresolved_dependency_count(self):
        graph = build_graph(missing_dep_data())
        report = analyze_graph(graph)
        assert report.unresolved_dependency_count == 1

    def test_no_root(self):
        graph = build_graph(no_root_data())
        report = analyze_graph(graph)
        assert report.direct_dependency_count == 0
        assert report.transitive_dependency_count == 0

    def test_fanout_ranking(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        # app has 2 deps (highest), react has 1, others have 0
        keys = [key for key, _ in report.top_packages_by_fanout]
        assert keys[0] == "app@1.0.0"
        assert report.top_packages_by_fanout[0][1] == 2

    def test_fanout_limit(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph, fanout_limit=2)
        assert len(report.top_packages_by_fanout) == 2

    def test_fanout_limit_zero(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph, fanout_limit=0)
        assert report.top_packages_by_fanout == []

    def test_fanout_limit_negative(self):
        graph = build_graph(simple_graph_data())
        with pytest.raises(ValueError, match="fanout_limit must be >= 0"):
            analyze_graph(graph, fanout_limit=-1)

    def test_fanout_deterministic_on_ties(self):
        """Nodes with equal fanout should be sorted alphabetically by key."""
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        # lodash and loose-envify both have 0 deps — should be alphabetical
        zero_fanout = [(k, c) for k, c in report.top_packages_by_fanout if c == 0]
        keys = [k for k, _ in zero_fanout]
        assert keys == sorted(keys)

    def test_leaf_package_count(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        # lodash and loose-envify are leaves
        assert report.leaf_package_count == 2

    def test_blast_radius_in_report(self):
        graph = build_graph(simple_graph_data())
        report = analyze_graph(graph)
        assert isinstance(report.top_packages_by_blast_radius, list)
        # root excluded by default, so all entries are non-root
        keys = [k for k, _, _ in report.top_packages_by_blast_radius]
        assert "app@1.0.0" not in keys

    def test_end_to_end_from_lockfile(self):
        normalized = parse_package_lock(LOCKFILE)
        graph = build_graph(normalized)
        report = analyze_graph(graph)
        assert report.total_nodes == 5
        assert report.direct_dependency_count == 2
        assert report.transitive_dependency_count == 4
        assert report.max_depth == 3
        assert report.has_cycle is False
        assert report.unresolved_dependency_count == 0


# ---------------------------------------------------------------------------
# Blast radius tests
# ---------------------------------------------------------------------------

def shared_transitive_data():
    """
    app -> A -> C
    app -> B -> C
    C -> D
    """
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {"name": "app", "version": "1.0.0", "dependencies": ["A@1.0.0", "B@1.0.0"]},
            "A@1.0.0": {"name": "A", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "B@1.0.0": {"name": "B", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "C@1.0.0": {"name": "C", "version": "1.0.0", "dependencies": ["D@1.0.0"]},
            "D@1.0.0": {"name": "D", "version": "1.0.0", "dependencies": []},
        },
    }


def cycle_data():
    """a -> b -> c -> a."""
    return {
        "root": "a@1.0.0",
        "packages": {
            "a@1.0.0": {"name": "a", "version": "1.0.0", "dependencies": ["b@1.0.0"]},
            "b@1.0.0": {"name": "b", "version": "1.0.0", "dependencies": ["c@1.0.0"]},
            "c@1.0.0": {"name": "c", "version": "1.0.0", "dependencies": ["a@1.0.0"]},
        },
    }


class TestBlastRadius:
    def test_basic_leaf(self):
        """A leaf package affects its ancestors only."""
        graph = build_graph(simple_graph_data())
        # loose-envify is depended on by react, which is depended on by app
        count, frac = compute_blast_radius(graph, "loose-envify@1.4.0")
        assert count == 2  # react, app
        assert frac == 2 / 4

    def test_shared_node(self):
        """C is depended on by A and B, both depended on by app."""
        graph = build_graph(shared_transitive_data())
        count, frac = compute_blast_radius(graph, "C@1.0.0")
        assert count == 3  # A, B, app
        assert frac == 3 / 5

    def test_deep_leaf(self):
        """D is the deepest leaf — affects C, A, B, app."""
        graph = build_graph(shared_transitive_data())
        count, frac = compute_blast_radius(graph, "D@1.0.0")
        assert count == 4  # C, A, B, app
        assert frac == 4 / 5

    def test_include_self(self):
        graph = build_graph(shared_transitive_data())
        count, frac = compute_blast_radius(graph, "C@1.0.0", include_self=True)
        assert count == 4  # C, A, B, app
        assert frac == 4 / 5

    def test_root_has_zero_blast(self):
        """Root has no dependents — blast radius is 0."""
        graph = build_graph(shared_transitive_data())
        count, frac = compute_blast_radius(graph, "app@1.0.0")
        assert count == 0
        assert frac == 0.0

    def test_nonexistent_package(self):
        graph = build_graph(shared_transitive_data())
        count, frac = compute_blast_radius(graph, "nope@0.0.0")
        assert count == 0
        assert frac == 0.0

    def test_cycle_safety(self):
        """Blast radius on cyclic graph should not infinite loop."""
        graph = build_graph(cycle_data())
        count, frac = compute_blast_radius(graph, "c@1.0.0")
        # c -> a (dependent), a -> ... but a also depends on b which depends on c
        # Upward from c: a is dependent of c, b is dependent of a (via cycle back)
        # Actually: a depends on b, b depends on c, c depends on a
        # dependents of c: b (b depends on c? No — b depends on c means c is dep of b? No.)
        # Let me think: b@1.0.0 dependencies: [c@1.0.0], so b depends on c, so c.dependents = [b]
        # a@1.0.0 dependencies: [b@1.0.0], so b.dependents = [a]
        # c@1.0.0 dependencies: [a@1.0.0], so a.dependents = [c]
        # Upward from c: dependents=[b], b.dependents=[a], a.dependents=[c] (already visited)
        assert count == 2  # b, a
        assert frac == 2 / 3


class TestBlastRadiusRanking:
    def test_root_excluded_by_default(self):
        graph = build_graph(shared_transitive_data())
        ranking = top_packages_by_blast_radius(graph)
        keys = [k for k, _, _ in ranking]
        assert "app@1.0.0" not in keys

    def test_root_included_when_requested(self):
        graph = build_graph(shared_transitive_data())
        ranking = top_packages_by_blast_radius(graph, exclude_root=False)
        keys = [k for k, _, _ in ranking]
        assert "app@1.0.0" in keys

    def test_ranking_order(self):
        """Packages should be sorted by affected count desc, then key asc."""
        graph = build_graph(shared_transitive_data())
        ranking = top_packages_by_blast_radius(graph)
        # D affects 4 (C,A,B,app), C affects 3 (A,B,app), A affects 1 (app), B affects 1 (app)
        assert ranking[0][0] == "D@1.0.0"
        assert ranking[0][1] == 4
        assert ranking[1][0] == "C@1.0.0"
        assert ranking[1][1] == 3
        # A and B tie at 1 — alphabetical
        assert ranking[2][0] == "A@1.0.0"
        assert ranking[3][0] == "B@1.0.0"

    def test_limit_zero(self):
        graph = build_graph(shared_transitive_data())
        assert top_packages_by_blast_radius(graph, limit=0) == []

    def test_limit_negative(self):
        graph = build_graph(shared_transitive_data())
        with pytest.raises(ValueError, match="limit must be >= 0"):
            top_packages_by_blast_radius(graph, limit=-1)

    def test_limit_truncates(self):
        graph = build_graph(shared_transitive_data())
        ranking = top_packages_by_blast_radius(graph, limit=2)
        assert len(ranking) == 2


# ---------------------------------------------------------------------------
# Removal simulation tests
# ---------------------------------------------------------------------------

class TestRemovalSimulation:
    def test_basic_removal_metrics(self):
        """Removing C from shared graph: app, A, B remain (3 nodes)."""
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "C@1.0.0")
        assert result.package_found is True
        assert result.before_report.total_nodes == 5
        assert result.after_report.total_nodes == 3  # app, A, B
        assert result.removed_subgraph_node_count == 2  # C, D gone

    def test_removal_affects_depth(self):
        """Removing C should reduce max depth from 3 to 1."""
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "C@1.0.0")
        assert result.before_report.max_depth == 3
        assert result.after_report.max_depth == 1  # app -> A, app -> B

    def test_removal_affects_transitive(self):
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "C@1.0.0")
        assert result.before_report.transitive_dependency_count == 4
        assert result.after_report.transitive_dependency_count == 2  # A, B

    def test_nonexistent_package(self):
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "nope@0.0.0")
        assert result.package_found is False
        assert result.before_report.total_nodes == result.after_report.total_nodes

    def test_remove_root(self):
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "app@1.0.0")
        assert result.package_found is True
        assert result.after_report.total_nodes == 0

    def test_remove_leaf(self):
        """Removing D from shared graph: app, A, B, C remain."""
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "D@1.0.0")
        assert result.after_report.total_nodes == 4
        assert result.removed_subgraph_node_count == 1

    def test_cycle_safety(self):
        graph = build_graph(cycle_data())
        result = analyze_removal_impact(graph, "b@1.0.0")
        assert result.package_found is True
        # Only a reachable after removing b
        assert result.after_report.total_nodes == 1

    def test_top_impacted_ordering(self):
        """Top impacted should be sorted by lost count desc, then key asc."""
        graph = build_graph(shared_transitive_data())
        # Remove C: dependents are A and B. Both lose C and D (2 each).
        result = analyze_removal_impact(graph, "C@1.0.0")
        keys = [k for k, _ in result.top_impacted_packages]
        # A and B tie — alphabetical
        assert keys == ["A@1.0.0", "B@1.0.0"]
        # Both lose the same count
        assert result.top_impacted_packages[0][1] == result.top_impacted_packages[1][1]

    def test_top_impacted_empty_for_nonexistent(self):
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "nope@0.0.0")
        assert result.top_impacted_packages == []

    def test_top_impacted_stable_on_ties(self):
        """Deterministic: same input always produces same order."""
        graph = build_graph(shared_transitive_data())
        r1 = analyze_removal_impact(graph, "C@1.0.0")
        r2 = analyze_removal_impact(graph, "C@1.0.0")
        assert r1.top_impacted_packages == r2.top_impacted_packages

    def test_depth_reduced_on_removal(self):
        """Removing C reduces depth from 3 to 1."""
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "C@1.0.0")
        assert result.before_report.max_depth == 3
        assert result.after_report.max_depth == 1

    def test_depth_unchanged_on_removal(self):
        """Removing a non-deepest-path node keeps depth the same.

        Graph: app -> A -> C -> D, app -> B -> C -> D
        Removing B does not change max depth (app -> A -> C -> D still exists).
        """
        graph = build_graph(shared_transitive_data())
        result = analyze_removal_impact(graph, "B@1.0.0")
        assert result.before_report.max_depth == 3
        assert result.after_report.max_depth == 3
