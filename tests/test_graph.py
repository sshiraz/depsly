"""Tests for core.graph — model, builder, traversal, and stats."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import (
    build_graph,
    collect_transitive_deps,
    graph_stats,
    has_cycle,
    max_depth,
    traverse_bfs,
    traverse_dfs,
    GraphBuildError,
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
                "dependencies": [],
            },
            "lodash@4.17.21": {
                "name": "lodash",
                "version": "4.17.21",
                "dependencies": [],
            },
        },
    }


def deep_chain_data():
    """a -> b -> c -> d (depth 3)."""
    return {
        "root": "a@1.0.0",
        "packages": {
            "a@1.0.0": {"name": "a", "version": "1.0.0", "dependencies": ["b@1.0.0"]},
            "b@1.0.0": {"name": "b", "version": "1.0.0", "dependencies": ["c@1.0.0"]},
            "c@1.0.0": {"name": "c", "version": "1.0.0", "dependencies": ["d@1.0.0"]},
            "d@1.0.0": {"name": "d", "version": "1.0.0", "dependencies": []},
        },
    }


def shared_transitive_data():
    """
    app -> A -> C
    app -> B -> C
    C -> D

    C is shared. Max depth from app is 3 (app -> A/B -> C -> D).
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


def missing_dep_data():
    """app depends on a package not listed in packages."""
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


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_simple_construction(self):
        g = build_graph(simple_graph_data())
        assert len(g.nodes) == 3
        assert g.root is not None
        assert g.root.key == "app@1.0.0"
        assert len(g.root.dependencies) == 2

    def test_nodes_created_once(self):
        g = build_graph(shared_transitive_data())
        # C is referenced by both A and B but only one node exists
        assert len([k for k in g.nodes if k.startswith("C@")]) == 1
        a_deps = {d.key for d in g.nodes["A@1.0.0"].dependencies}
        b_deps = {d.key for d in g.nodes["B@1.0.0"].dependencies}
        assert "C@1.0.0" in a_deps
        assert "C@1.0.0" in b_deps
        # Same object in memory
        assert g.nodes["A@1.0.0"].dependencies[0] is g.nodes["B@1.0.0"].dependencies[0]

    def test_missing_dependency_tracked(self):
        g = build_graph(missing_dep_data())
        assert "ghost@0.0.1" in g.missing_keys
        assert len(g.root.dependencies) == 0

    def test_empty_packages(self):
        g = build_graph({"root": "x@1.0.0", "packages": {}})
        assert len(g.nodes) == 0
        assert g.root is None

    def test_invalid_packages_type(self):
        with pytest.raises(GraphBuildError, match="must be a dict"):
            build_graph({"packages": "bad"})

    def test_missing_name_field(self):
        with pytest.raises(GraphBuildError, match="missing required field 'name'"):
            build_graph({"packages": {"x@1.0.0": {"version": "1.0.0"}}})

    def test_missing_version_field(self):
        with pytest.raises(GraphBuildError, match="missing required field 'version'"):
            build_graph({"packages": {"x@1.0.0": {"name": "x"}}})

    def test_invalid_dependencies_type(self):
        with pytest.raises(GraphBuildError, match="dependencies must be a list"):
            build_graph({
                "packages": {
                    "x@1.0.0": {"name": "x", "version": "1.0.0", "dependencies": "bad"},
                }
            })

    def test_invalid_package_entry_type(self):
        with pytest.raises(GraphBuildError, match="must be a dict"):
            build_graph({"packages": {"x@1.0.0": "bad"}})


# ---------------------------------------------------------------------------
# Traversal tests
# ---------------------------------------------------------------------------

class TestTraversal:
    def test_dfs_simple(self):
        g = build_graph(simple_graph_data())
        order = traverse_dfs(g)
        assert order[0] == "app@1.0.0"
        assert set(order) == {"app@1.0.0", "react@18.2.0", "lodash@4.17.21"}

    def test_bfs_simple(self):
        g = build_graph(simple_graph_data())
        order = traverse_bfs(g)
        assert order[0] == "app@1.0.0"
        # BFS: root first, then its direct deps
        assert set(order[1:]) == {"react@18.2.0", "lodash@4.17.21"}

    def test_dfs_with_cycle(self):
        g = build_graph(cycle_data())
        order = traverse_dfs(g)
        assert len(order) == 3  # visits each node exactly once

    def test_bfs_with_cycle(self):
        g = build_graph(cycle_data())
        order = traverse_bfs(g)
        assert len(order) == 3

    def test_traversal_nonexistent_start(self):
        g = build_graph(simple_graph_data())
        assert traverse_dfs(g, "nope@0.0.0") == []
        assert traverse_bfs(g, "nope@0.0.0") == []

    def test_transitive_deps_simple(self):
        g = build_graph(simple_graph_data())
        deps = collect_transitive_deps(g)
        assert deps == {"react@18.2.0", "lodash@4.17.21"}

    def test_transitive_deps_deep(self):
        g = build_graph(deep_chain_data())
        deps = collect_transitive_deps(g)
        assert deps == {"b@1.0.0", "c@1.0.0", "d@1.0.0"}

    def test_transitive_deps_shared(self):
        g = build_graph(shared_transitive_data())
        deps = collect_transitive_deps(g)
        assert deps == {"A@1.0.0", "B@1.0.0", "C@1.0.0", "D@1.0.0"}

    def test_transitive_deps_with_cycle(self):
        g = build_graph(cycle_data())
        deps = collect_transitive_deps(g)
        # a is start node — must be excluded even though c -> a cycles back
        assert "a@1.0.0" not in deps
        assert deps == {"b@1.0.0", "c@1.0.0"}

    def test_transitive_deps_excludes_start(self):
        g = build_graph(simple_graph_data())
        deps = collect_transitive_deps(g)
        assert "app@1.0.0" not in deps


# ---------------------------------------------------------------------------
# Stats tests
# ---------------------------------------------------------------------------

class TestStats:
    def test_no_cycle_in_simple(self):
        g = build_graph(simple_graph_data())
        assert has_cycle(g) is False

    def test_cycle_detected(self):
        g = build_graph(cycle_data())
        assert has_cycle(g) is True

    def test_no_cycle_in_shared(self):
        g = build_graph(shared_transitive_data())
        assert has_cycle(g) is False

    def test_max_depth_simple(self):
        g = build_graph(simple_graph_data())
        assert max_depth(g) == 1

    def test_max_depth_chain(self):
        g = build_graph(deep_chain_data())
        assert max_depth(g) == 3

    def test_max_depth_shared_transitive(self):
        """Shared node C must not suppress the deeper path through it."""
        g = build_graph(shared_transitive_data())
        assert max_depth(g) == 3  # app -> A -> C -> D

    def test_max_depth_with_cycle(self):
        g = build_graph(cycle_data())
        depth = max_depth(g)
        assert depth >= 0  # doesn't hang or crash
        assert depth == 2  # a -> b -> c, back-edge to a ignored

    def test_max_depth_nonexistent(self):
        g = build_graph(simple_graph_data())
        assert max_depth(g, "nope@0.0.0") == -1

    def test_graph_stats(self):
        g = build_graph(simple_graph_data())
        stats = graph_stats(g)
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["max_depth"] == 1
        assert stats["has_cycle"] is False

    def test_graph_stats_shared(self):
        g = build_graph(shared_transitive_data())
        stats = graph_stats(g)
        assert stats["total_nodes"] == 5
        # app->A, app->B, A->C, B->C, C->D = 5 edges
        assert stats["total_edges"] == 5
        assert stats["max_depth"] == 3
        assert stats["has_cycle"] is False
