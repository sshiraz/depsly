"""Tests for core.analyze — structural graph analysis."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from core.ingestion import parse_package_lock
from core.analyze import analyze_graph


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
