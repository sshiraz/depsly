"""Tests for core.ingestion — package-lock.json parsing."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.ingestion import parse_package_lock, IngestionError
from core.graph import build_graph, collect_transitive_deps, graph_stats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_LOCKFILE = json.dumps({
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

SCOPED_LOCKFILE = json.dumps({
    "name": "my-app",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "my-app",
            "version": "1.0.0",
            "dependencies": {
                "@babel/core": "^7.20.0"
            }
        },
        "node_modules/@babel/core": {
            "version": "7.20.12",
            "dependencies": {
                "@babel/parser": "^7.20.0"
            }
        },
        "node_modules/@babel/parser": {
            "version": "7.20.15"
        }
    }
})

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

MINIMAL_LOCKFILE = json.dumps({
    "name": "empty-app",
    "version": "0.0.1",
    "lockfileVersion": 3,
    "packages": {
        "": {
            "name": "empty-app",
            "version": "0.0.1"
        }
    }
})


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestParsePackageLock:
    def test_simple_lockfile(self):
        result = parse_package_lock(SIMPLE_LOCKFILE)
        assert result["root"] == "my-app@1.0.0"
        assert "my-app@1.0.0" in result["packages"]
        assert "react@18.2.0" in result["packages"]
        assert "lodash@4.17.21" in result["packages"]
        assert "loose-envify@1.4.0" in result["packages"]
        assert "js-tokens@4.0.0" in result["packages"]

    def test_root_dependencies_resolved(self):
        result = parse_package_lock(SIMPLE_LOCKFILE)
        root = result["packages"]["my-app@1.0.0"]
        assert "react@18.2.0" in root["dependencies"]
        assert "lodash@4.17.21" in root["dependencies"]

    def test_transitive_dependencies_resolved(self):
        result = parse_package_lock(SIMPLE_LOCKFILE)
        react = result["packages"]["react@18.2.0"]
        assert "loose-envify@1.4.0" in react["dependencies"]

    def test_leaf_has_no_dependencies(self):
        result = parse_package_lock(SIMPLE_LOCKFILE)
        lodash = result["packages"]["lodash@4.17.21"]
        assert lodash["dependencies"] == []

    def test_scoped_packages(self):
        result = parse_package_lock(SCOPED_LOCKFILE)
        assert "@babel/core@7.20.12" in result["packages"]
        assert "@babel/parser@7.20.15" in result["packages"]
        core = result["packages"]["@babel/core@7.20.12"]
        assert "@babel/parser@7.20.15" in core["dependencies"]

    def test_dev_dependencies_included_for_root(self):
        result = parse_package_lock(DEV_DEPS_LOCKFILE)
        root = result["packages"]["my-app@1.0.0"]
        assert "react@18.2.0" in root["dependencies"]
        assert "typescript@5.3.3" in root["dependencies"]

    def test_minimal_lockfile(self):
        result = parse_package_lock(MINIMAL_LOCKFILE)
        assert result["root"] == "empty-app@0.0.1"
        assert len(result["packages"]) == 1

    def test_unsupported_lockfile_version(self):
        bad = json.dumps({"lockfileVersion": 1, "packages": {}})
        with pytest.raises(IngestionError, match="Unsupported lockfileVersion"):
            parse_package_lock(bad)

    def test_missing_root_entry(self):
        bad = json.dumps({"lockfileVersion": 3, "packages": {
            "node_modules/react": {"version": "18.0.0"}
        }})
        with pytest.raises(IngestionError, match="no root entry"):
            parse_package_lock(bad)

    def test_dev_dependencies_excluded(self):
        result = parse_package_lock(DEV_DEPS_LOCKFILE, include_dev=False)
        root = result["packages"]["my-app@1.0.0"]
        assert "react@18.2.0" in root["dependencies"]
        assert "typescript@5.3.3" not in root["dependencies"]

    def test_unresolved_dependencies_tracked(self):
        lockfile = json.dumps({
            "name": "my-app",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "my-app",
                    "version": "1.0.0",
                    "dependencies": {"react": "^18.0.0", "ghost-pkg": "^1.0.0"}
                },
                "node_modules/react": {"version": "18.2.0"}
            }
        })
        result = parse_package_lock(lockfile)
        root = result["packages"]["my-app@1.0.0"]
        assert "react@18.2.0" in root["dependencies"]
        assert "ghost-pkg" in root["unresolved_dependencies"]

    def test_invalid_packages_type(self):
        bad = json.dumps({"lockfileVersion": 3, "packages": "bad"})
        with pytest.raises(IngestionError, match="must be a dict"):
            parse_package_lock(bad)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(IngestionError, match="File not found"):
            parse_package_lock(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# Integration: parse -> build_graph
# ---------------------------------------------------------------------------

class TestIngestionToGraph:
    def test_simple_end_to_end(self):
        normalized = parse_package_lock(SIMPLE_LOCKFILE)
        graph = build_graph(normalized)
        assert graph.root is not None
        assert graph.root.key == "my-app@1.0.0"
        assert len(graph.nodes) == 5
        assert len(graph.missing_keys) == 0

    def test_transitive_deps_correct(self):
        normalized = parse_package_lock(SIMPLE_LOCKFILE)
        graph = build_graph(normalized)
        deps = collect_transitive_deps(graph)
        assert deps == {
            "react@18.2.0",
            "lodash@4.17.21",
            "loose-envify@1.4.0",
            "js-tokens@4.0.0",
        }

    def test_graph_stats(self):
        normalized = parse_package_lock(SIMPLE_LOCKFILE)
        graph = build_graph(normalized)
        stats = graph_stats(graph)
        assert stats["total_nodes"] == 5
        assert stats["has_cycle"] is False
        # my-app -> react -> loose-envify -> js-tokens = depth 3
        assert stats["max_depth"] == 3

    def test_real_lockfile(self):
        """Integration test against the actual frontend lockfile."""
        from pathlib import Path
        lockfile_path = Path(__file__).parent.parent / "frontend" / "package-lock.json"
        if not lockfile_path.exists():
            pytest.skip("frontend/package-lock.json not present")

        normalized = parse_package_lock(lockfile_path)
        graph = build_graph(normalized)

        assert graph.root is not None
        assert len(graph.nodes) > 0
        assert not graph_stats(graph)["has_cycle"]
