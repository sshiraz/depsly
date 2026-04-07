"""Tests for core.classify."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.classify import classify_all_packages, classify_package
from core.graph import build_graph
from core.ingestion import parse_package_lock


def shared_transitive_data():
    return {
        "root": "app@1.0.0",
        "packages": {
            "app@1.0.0": {"name": "app", "version": "1.0.0", "dependencies": ["A@1.0.0", "B@1.0.0"]},
            "A@1.0.0": {"name": "A", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "B@1.0.0": {"name": "B", "version": "1.0.0", "dependencies": ["C@1.0.0"]},
            "C@1.0.0": {"name": "C", "version": "1.0.0", "dependencies": []},
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
            "dependencies": {
                "react": "^18.2.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0"
            }
        },
        "node_modules/react": {
            "version": "18.2.0"
        },
        "node_modules/typescript": {
            "version": "5.3.3"
        }
    }
})


class TestClassifyPackage:
    def test_classifies_root(self):
        graph = build_graph(shared_transitive_data())
        result = classify_package(graph, "app@1.0.0")
        assert result.is_root is True
        assert result.is_direct_dependency is False
        assert result.is_transitive_dependency is False
        assert result.parent_count == 0
        assert result.depth_from_root == 0

    def test_classifies_direct_dependency(self):
        graph = build_graph(shared_transitive_data())
        result = classify_package(graph, "A@1.0.0")
        assert result.is_root is False
        assert result.is_direct_dependency is True
        assert result.is_transitive_dependency is False
        assert result.parent_count == 1
        assert result.depth_from_root == 1

    def test_classifies_transitive_dependency(self):
        graph = build_graph(shared_transitive_data())
        result = classify_package(graph, "C@1.0.0")
        assert result.is_root is False
        assert result.is_direct_dependency is False
        assert result.is_transitive_dependency is True
        assert result.parent_count == 2
        assert result.depth_from_root == 2

    def test_missing_package(self):
        graph = build_graph(shared_transitive_data())
        result = classify_package(graph, "missing@0.0.0")
        assert result.is_root is False
        assert result.is_direct_dependency is False
        assert result.is_transitive_dependency is False
        assert result.is_dev_dependency is None
        assert result.parent_count == 0
        assert result.depth_from_root is None

    def test_classifies_dev_dependency_when_metadata_available(self):
        normalized = parse_package_lock(DEV_DEPS_LOCKFILE)
        graph = build_graph(normalized)
        result = classify_package(graph, "typescript@5.3.3", normalized)
        assert result.is_direct_dependency is True
        assert result.is_dev_dependency is True
        assert result.depth_from_root == 1

    def test_non_dev_direct_dependency_is_false(self):
        normalized = parse_package_lock(DEV_DEPS_LOCKFILE)
        graph = build_graph(normalized)
        result = classify_package(graph, "react@18.2.0", normalized)
        assert result.is_direct_dependency is True
        assert result.is_dev_dependency is False


class TestClassifyAllPackages:
    def test_returns_all_packages_in_deterministic_order(self):
        graph = build_graph(shared_transitive_data())
        result = classify_all_packages(graph)
        assert list(result) == sorted(graph.nodes)
        assert set(result) == set(graph.nodes)
