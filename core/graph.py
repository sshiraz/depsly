"""Dependency graph model, builder, and traversal utilities."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class PackageNode:
    """A single package in the dependency graph."""

    name: str
    version: str
    key: str
    dependencies: list[PackageNode] = field(default_factory=list, repr=False)
    dependents: list[PackageNode] = field(default_factory=list, repr=False)

    def add_dependency(self, node: PackageNode) -> None:
        """Add a direct dependency if not already present."""
        if node not in self.dependencies:
            self.dependencies.append(node)

    def add_dependent(self, node: PackageNode) -> None:
        """Add a direct dependent if not already present."""
        if node not in self.dependents:
            self.dependents.append(node)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageNode):
            return NotImplemented
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)


@dataclass
class DependencyGraph:
    """Directed graph of package dependencies.

    Nodes are PackageNode instances keyed by their unique key (name@version).
    Edges are directed: a node's dependencies list points to its children.
    """

    nodes: dict[str, PackageNode] = field(default_factory=dict)
    root_key: str | None = None
    missing_keys: set[str] = field(default_factory=set)

    @property
    def root(self) -> PackageNode | None:
        """Return the root node, or None if unset."""
        if self.root_key is None:
            return None
        return self.nodes.get(self.root_key)

    def get(self, key: str) -> PackageNode | None:
        """Look up a node by key."""
        return self.nodes.get(key)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class GraphBuildError(Exception):
    """Raised when normalized input is malformed."""


def build_graph(data: dict) -> DependencyGraph:
    """Build a DependencyGraph from normalized input.

    Expected input shape:
        {
            "root": "my-app@1.0.0",
            "packages": {
                "my-app@1.0.0": {
                    "name": "my-app",
                    "version": "1.0.0",
                    "dependencies": ["react@18.2.0"]
                },
                ...
            }
        }

    Nodes are created once. Missing dependency references are tracked
    in graph.missing_keys rather than raising.
    """
    packages = data.get("packages", {})
    if not isinstance(packages, dict):
        raise GraphBuildError("'packages' must be a dict")

    graph = DependencyGraph(root_key=data.get("root"))

    # Pass 1: create all nodes
    for key, info in packages.items():
        if not isinstance(info, dict):
            raise GraphBuildError(f"Package entry '{key}' must be a dict, got {type(info).__name__}")
        if "name" not in info:
            raise GraphBuildError(f"Package '{key}' missing required field 'name'")
        if "version" not in info:
            raise GraphBuildError(f"Package '{key}' missing required field 'version'")

        graph.nodes[key] = PackageNode(
            name=info["name"],
            version=info["version"],
            key=key,
        )

    # Pass 2: wire edges
    for key, info in packages.items():
        node = graph.nodes[key]
        deps = info.get("dependencies", [])
        if not isinstance(deps, list):
            raise GraphBuildError(
                f"Package '{key}' dependencies must be a list, got {type(deps).__name__}"
            )
        for dep_key in deps:
            dep_node = graph.nodes.get(dep_key)
            if dep_node is None:
                graph.missing_keys.add(dep_key)
            else:
                node.add_dependency(dep_node)
                dep_node.add_dependent(node)

    return graph


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

def traverse_dfs(graph: DependencyGraph, start_key: str | None = None) -> list[str]:
    """Depth-first traversal from start_key (default: root). Returns keys in visit order.

    Cycle-safe: each node is visited at most once.
    """
    start = start_key or graph.root_key
    if start is None or start not in graph.nodes:
        return []

    visited: set[str] = set()
    order: list[str] = []
    stack = [graph.nodes[start]]

    while stack:
        node = stack.pop()
        if node.key in visited:
            continue
        visited.add(node.key)
        order.append(node.key)
        for dep in reversed(node.dependencies):
            if dep.key not in visited:
                stack.append(dep)

    return order


def traverse_bfs(graph: DependencyGraph, start_key: str | None = None) -> list[str]:
    """Breadth-first traversal from start_key (default: root). Returns keys in visit order.

    Cycle-safe: each node is visited at most once.
    """
    start = start_key or graph.root_key
    if start is None or start not in graph.nodes:
        return []

    visited: set[str] = set()
    order: list[str] = []
    queue: deque[PackageNode] = deque([graph.nodes[start]])
    visited.add(start)

    while queue:
        node = queue.popleft()
        order.append(node.key)
        for dep in node.dependencies:
            if dep.key not in visited:
                visited.add(dep.key)
                queue.append(dep)

    return order


def collect_transitive_deps(graph: DependencyGraph, start_key: str | None = None) -> set[str]:
    """Return the set of all transitive dependency keys reachable from start_key.

    The start node itself is excluded from the result. Cycle-safe.
    """
    start = start_key or graph.root_key
    if start is None or start not in graph.nodes:
        return set()

    visited: set[str] = set()
    stack = list(graph.nodes[start].dependencies)

    while stack:
        node = stack.pop()
        if node.key in visited:
            continue
        visited.add(node.key)
        for dep in node.dependencies:
            if dep.key not in visited:
                stack.append(dep)

    visited.discard(start)
    return visited


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def has_cycle(graph: DependencyGraph) -> bool:
    """Detect whether the graph contains any cycle.

    Uses iterative DFS with white/gray/black coloring.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {k: WHITE for k in graph.nodes}

    for start_key in graph.nodes:
        if color[start_key] != WHITE:
            continue

        stack: list[tuple[PackageNode, int]] = [(graph.nodes[start_key], 0)]
        color[start_key] = GRAY

        while stack:
            node, idx = stack.pop()

            if idx < len(node.dependencies):
                stack.append((node, idx + 1))
                child = node.dependencies[idx]

                if color[child.key] == GRAY:
                    return True
                if color[child.key] == WHITE:
                    color[child.key] = GRAY
                    stack.append((child, 0))
            else:
                color[node.key] = BLACK

    return False


def max_depth(graph: DependencyGraph, start_key: str | None = None) -> int:
    """Calculate the maximum depth from start_key (default: root).

    Root is depth 0. Returns -1 if the start node doesn't exist.

    Uses memoized post-order DFS. Each node's depth is computed as
    1 + max(children depths), cached, and reused. This means shared
    transitive nodes return their full subtree depth every time they
    are referenced, rather than being skipped after first visit.

    Cycle-safe via an ancestor set (path stack) — back-edges are
    treated as depth 0 to break the cycle without suppressing
    legitimate deeper paths through shared nodes.
    """
    start = start_key or graph.root_key
    if start is None or start not in graph.nodes:
        return -1

    memo: dict[str, int] = {}
    # Iterative post-order DFS with ancestor tracking for cycle safety
    # Stack entries: (node, child_index, current_max_child_depth)
    stack: list[tuple[PackageNode, int, int]] = [(graph.nodes[start], 0, 0)]
    ancestors: set[str] = {start}

    while stack:
        node, idx, best_child = stack[-1]

        if idx < len(node.dependencies):
            # Advance to next child
            stack[-1] = (node, idx + 1, best_child)
            child = node.dependencies[idx]

            if child.key in ancestors:
                # Cycle back-edge: ignore
                continue
            if child.key in memo:
                # Already computed: reuse
                child_depth = memo[child.key]
                if child_depth + 1 > best_child:
                    stack[-1] = (node, idx + 1, child_depth + 1)
                continue

            # Recurse into child
            ancestors.add(child.key)
            stack.append((child, 0, 0))
        else:
            # All children processed — this node's subtree depth is best_child
            stack.pop()
            memo[node.key] = best_child
            ancestors.discard(node.key)

            # Propagate to parent
            if stack:
                parent_node, parent_idx, parent_best = stack[-1]
                if best_child + 1 > parent_best:
                    stack[-1] = (parent_node, parent_idx, best_child + 1)

    return memo.get(start, 0)


def graph_stats(graph: DependencyGraph) -> dict[str, int | bool]:
    """Compute summary statistics for the graph."""
    total_edges = sum(len(n.dependencies) for n in graph.nodes.values())
    return {
        "total_nodes": len(graph.nodes),
        "total_edges": total_edges,
        "max_depth": max_depth(graph),
        "has_cycle": has_cycle(graph),
    }
