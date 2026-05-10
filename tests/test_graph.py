"""Tests for core.graph — model, builder, traversal, and stats."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import (
    build_reverse_edges,
    build_graph,
    collect_transitive_deps,
    compute_dominator_subtree_sizes,
    graph_stats,
    has_cycle,
    max_depth,
    parent_counts,
    simulate_remove_package,
    shortest_depths_from_root,
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

    def test_dependents_simple(self):
        g = build_graph(simple_graph_data())
        react = g.nodes["react@18.2.0"]
        lodash = g.nodes["lodash@4.17.21"]
        assert g.root in react.dependents
        assert g.root in lodash.dependents
        # root has no dependents
        assert g.root.dependents == []

    def test_dependents_shared_node(self):
        g = build_graph(shared_transitive_data())
        c = g.nodes["C@1.0.0"]
        dependent_keys = {d.key for d in c.dependents}
        assert dependent_keys == {"A@1.0.0", "B@1.0.0"}

    def test_dependents_deep_chain(self):
        g = build_graph(deep_chain_data())
        d = g.nodes["d@1.0.0"]
        assert len(d.dependents) == 1
        assert d.dependents[0].key == "c@1.0.0"

    def test_graph_stats_shared(self):
        g = build_graph(shared_transitive_data())
        stats = graph_stats(g)
        assert stats["total_nodes"] == 5
        # app->A, app->B, A->C, B->C, C->D = 5 edges
        assert stats["total_edges"] == 5
        assert stats["max_depth"] == 3
        assert stats["has_cycle"] is False


# ---------------------------------------------------------------------------
# Reverse edges / shortest depth tests
# ---------------------------------------------------------------------------

class TestReverseEdgeUtilities:
    def test_build_reverse_edges_simple(self):
        g = build_graph(simple_graph_data())
        reverse = build_reverse_edges(g)
        assert reverse["app@1.0.0"] == set()
        assert reverse["react@18.2.0"] == {"app@1.0.0"}
        assert reverse["lodash@4.17.21"] == {"app@1.0.0"}

    def test_build_reverse_edges_shared_node(self):
        g = build_graph(shared_transitive_data())
        reverse = build_reverse_edges(g)
        assert reverse["C@1.0.0"] == {"A@1.0.0", "B@1.0.0"}
        assert reverse["D@1.0.0"] == {"C@1.0.0"}

    def test_parent_counts(self):
        g = build_graph(shared_transitive_data())
        counts = parent_counts(g)
        assert counts["app@1.0.0"] == 0
        assert counts["A@1.0.0"] == 1
        assert counts["B@1.0.0"] == 1
        assert counts["C@1.0.0"] == 2
        assert counts["D@1.0.0"] == 1


class TestShortestDepths:
    def test_shortest_depths_simple(self):
        g = build_graph(simple_graph_data())
        depths = shortest_depths_from_root(g)
        assert depths == {
            "app@1.0.0": 0,
            "lodash@4.17.21": 1,
            "react@18.2.0": 1,
        }

    def test_shortest_depths_shared_node(self):
        g = build_graph(shared_transitive_data())
        depths = shortest_depths_from_root(g)
        assert depths["app@1.0.0"] == 0
        assert depths["A@1.0.0"] == 1
        assert depths["B@1.0.0"] == 1
        assert depths["C@1.0.0"] == 2
        assert depths["D@1.0.0"] == 3

    def test_shortest_depths_with_cycle(self):
        g = build_graph(cycle_data())
        depths = shortest_depths_from_root(g)
        assert depths == {
            "a@1.0.0": 0,
            "b@1.0.0": 1,
            "c@1.0.0": 2,
        }

    def test_shortest_depths_missing_root(self):
        g = build_graph({"root": "missing@1.0.0", "packages": simple_graph_data()["packages"]})
        assert shortest_depths_from_root(g) == {}


# ---------------------------------------------------------------------------
# Simulate remove tests
# ---------------------------------------------------------------------------

class TestSimulateRemove:
    def test_remove_leaf_in_chain(self):
        """a -> b -> c -> d: removing d leaves a, b, c."""
        g = build_graph(deep_chain_data())
        sim = simulate_remove_package(g, "d@1.0.0")
        assert set(sim.nodes.keys()) == {"a@1.0.0", "b@1.0.0", "c@1.0.0"}
        # c no longer has dependencies
        assert sim.nodes["c@1.0.0"].dependencies == []

    def test_remove_middle_of_chain(self):
        """a -> b -> c -> d: removing b makes c, d unreachable."""
        g = build_graph(deep_chain_data())
        sim = simulate_remove_package(g, "b@1.0.0")
        assert set(sim.nodes.keys()) == {"a@1.0.0"}

    def test_remove_shared_node(self):
        """app -> A -> C, app -> B -> C, C -> D: removing C leaves app, A, B."""
        g = build_graph(shared_transitive_data())
        sim = simulate_remove_package(g, "C@1.0.0")
        assert set(sim.nodes.keys()) == {"app@1.0.0", "A@1.0.0", "B@1.0.0"}

    def test_remove_nonexistent(self):
        """Removing a nonexistent package returns the reachable graph unchanged."""
        g = build_graph(simple_graph_data())
        sim = simulate_remove_package(g, "nope@0.0.0")
        assert set(sim.nodes.keys()) == set(g.nodes.keys())

    def test_remove_root(self):
        """Removing root yields an empty graph."""
        g = build_graph(simple_graph_data())
        sim = simulate_remove_package(g, "app@1.0.0")
        assert len(sim.nodes) == 0

    def test_cycle_safety(self):
        """a -> b -> c -> a: removing b should not loop."""
        g = build_graph(cycle_data())
        sim = simulate_remove_package(g, "b@1.0.0")
        # Only a is reachable (c depends on a, but a can't reach c without b)
        assert set(sim.nodes.keys()) == {"a@1.0.0"}

    def test_does_not_mutate_original(self):
        g = build_graph(shared_transitive_data())
        original_keys = set(g.nodes.keys())
        simulate_remove_package(g, "C@1.0.0")
        assert set(g.nodes.keys()) == original_keys

    def test_reverse_edges_wired(self):
        """Simulated graph should have correct dependents."""
        g = build_graph(shared_transitive_data())
        sim = simulate_remove_package(g, "D@1.0.0")
        # C should still exist with dependents A and B
        c = sim.nodes["C@1.0.0"]
        dependent_keys = {d.key for d in c.dependents}
        assert dependent_keys == {"A@1.0.0", "B@1.0.0"}


class TestComputeDominatorSubtreeSizes:
    """Each size should equal simulate_remove_package's removed_count."""

    def test_chain(self):
        """app -> a -> b -> c: removing a removes {a,b,c}, b removes {b,c}, c removes {c}."""
        data = {
            "root": "app@1",
            "packages": {
                "app@1": {"name": "app", "version": "1", "dependencies": ["a@1"]},
                "a@1": {"name": "a", "version": "1", "dependencies": ["b@1"]},
                "b@1": {"name": "b", "version": "1", "dependencies": ["c@1"]},
                "c@1": {"name": "c", "version": "1", "dependencies": []},
            },
        }
        sizes = compute_dominator_subtree_sizes(build_graph(data))
        assert sizes["a@1"] == 3
        assert sizes["b@1"] == 2
        assert sizes["c@1"] == 1

    def test_shared_dep_not_dominated(self):
        """app -> A -> shared, app -> B -> shared. Removing A leaves shared reachable."""
        data = {
            "root": "app@1",
            "packages": {
                "app@1": {"name": "app", "version": "1", "dependencies": ["A@1", "B@1"]},
                "A@1": {"name": "A", "version": "1", "dependencies": ["shared@1"]},
                "B@1": {"name": "B", "version": "1", "dependencies": ["shared@1"]},
                "shared@1": {"name": "shared", "version": "1", "dependencies": []},
            },
        }
        sizes = compute_dominator_subtree_sizes(build_graph(data))
        assert sizes["A@1"] == 1
        assert sizes["B@1"] == 1
        assert sizes["shared@1"] == 1

    def test_root_dominates_everything(self):
        data = {
            "root": "app@1",
            "packages": {
                "app@1": {"name": "app", "version": "1", "dependencies": ["a@1"]},
                "a@1": {"name": "a", "version": "1", "dependencies": []},
            },
        }
        sizes = compute_dominator_subtree_sizes(build_graph(data))
        assert sizes["app@1"] == 2

    def test_no_root(self):
        g = build_graph({"root": None, "packages": {}})
        assert compute_dominator_subtree_sizes(g) == {}

    def test_cycle_safe(self):
        """a -> b -> c -> a: starting from app -> a, dom sizes should not loop."""
        data = {
            "root": "app@1",
            "packages": {
                "app@1": {"name": "app", "version": "1", "dependencies": ["a@1"]},
                "a@1": {"name": "a", "version": "1", "dependencies": ["b@1"]},
                "b@1": {"name": "b", "version": "1", "dependencies": ["c@1"]},
                "c@1": {"name": "c", "version": "1", "dependencies": ["a@1"]},
            },
        }
        sizes = compute_dominator_subtree_sizes(build_graph(data))
        # All of a, b, c are dominated by a (only path from root passes through a)
        assert sizes["a@1"] == 3
        assert sizes["b@1"] == 2
        assert sizes["c@1"] == 1

    def test_matches_simulate_remove_on_real_lockfile(self):
        """Cross-check on a non-trivial real graph."""
        from pathlib import Path
        from core.ingestion import parse_package_lock
        from core.simulate import simulate_remove

        lock = Path(__file__).parent.parent / "frontend" / "package-lock.json"
        if not lock.exists():
            pytest.skip("frontend lockfile fixture not available")
        g = build_graph(parse_package_lock(lock))
        sizes = compute_dominator_subtree_sizes(g)
        before = set(traverse_bfs(g))
        # Spot-check 10 nodes
        sample = sorted(g.nodes)[:10]
        for key in sample:
            if key == g.root_key: continue
            sim = simulate_remove(g, key, before_keys=before)
            assert sizes[key] == sim.removed_count, f"mismatch on {key}"

