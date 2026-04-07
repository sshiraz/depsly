"""Tests for core.trace."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import build_graph
from core.trace import trace_package


def direct_graph_data():
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


def shared_transitive_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["A@1.0.0", "B@1.0.0"],
            },
            "A@1.0.0": {
                "name": "A",
                "version": "1.0.0",
                "dependencies": ["C@1.0.0"],
            },
            "B@1.0.0": {
                "name": "B",
                "version": "1.0.0",
                "dependencies": ["C@1.0.0"],
            },
            "C@1.0.0": {
                "name": "C",
                "version": "1.0.0",
                "dependencies": [],
            },
        },
    }


def shorter_and_longer_path_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {
                "name": "app",
                "version": "1.0.0",
                "dependencies": ["A@1.0.0", "B@1.0.0"],
            },
            "A@1.0.0": {
                "name": "A",
                "version": "1.0.0",
                "dependencies": ["D@1.0.0"],
            },
            "B@1.0.0": {
                "name": "B",
                "version": "1.0.0",
                "dependencies": ["C@1.0.0"],
            },
            "C@1.0.0": {
                "name": "C",
                "version": "1.0.0",
                "dependencies": ["D@1.0.0"],
            },
            "D@1.0.0": {
                "name": "D",
                "version": "1.0.0",
                "dependencies": [],
            },
        },
    }


class TestTracePackage:
    def test_direct_dependency_path(self):
        graph = build_graph(direct_graph_data())
        result = trace_package(graph, "react@18.2.0")
        assert result.package_found is True
        assert result.reachable_from_root is True
        assert result.paths == (("app@1.0.0", "react@18.2.0"),)

    def test_transitive_dependency_shortest_path(self):
        graph = build_graph(shorter_and_longer_path_data())
        result = trace_package(graph, "D@1.0.0")
        assert result.paths == (("app@1.0.0", "A@1.0.0", "D@1.0.0"),)

    def test_multiple_paths_are_deterministic(self):
        graph = build_graph(shared_transitive_data())
        result = trace_package(graph, "C@1.0.0")
        assert result.paths == (
            ("app@1.0.0", "A@1.0.0", "C@1.0.0"),
            ("app@1.0.0", "B@1.0.0", "C@1.0.0"),
        )

    def test_multiple_paths_respects_limit(self):
        graph = build_graph(shared_transitive_data())
        result = trace_package(graph, "C@1.0.0", max_paths=1)
        assert result.paths == (("app@1.0.0", "A@1.0.0", "C@1.0.0"),)

    def test_unreachable_package(self):
        graph = build_graph(shared_transitive_data())
        result = trace_package(graph, "missing@0.0.0")
        assert result.package_found is False
        assert result.reachable_from_root is False
        assert result.paths == ()

    def test_negative_limit_raises(self):
        graph = build_graph(shared_transitive_data())
        with pytest.raises(ValueError, match="max_paths must be >= 0"):
            trace_package(graph, "C@1.0.0", max_paths=-1)
