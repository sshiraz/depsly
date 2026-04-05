# Graph Semantics

This document defines the semantic contracts for Depsly's dependency graph. All traversal, analysis, and scoring code must respect these definitions.

---

## Node

A **node** represents a unique package at a specific version.

- Identity: `name@version` (the **key**)
- Two entries with the same key are the same node
- A node is created exactly once per graph, even if referenced by multiple parents

## Edge

A **dependency edge** is a directed edge from a parent package to a child package.

- Direction: parent -> dependency
- Meaning: "parent requires dependency"
- An edge does not imply exclusivity — multiple parents can share the same dependency

## Transitive Dependency

A **transitive dependency** of node `X` is any node reachable from `X` by following dependency edges, **excluding `X` itself**.

- `collect_transitive_deps(graph, "X")` never includes `"X"` in the result
- This holds regardless of graph shape, including cycles
- A package cannot be its own transitive dependency

## Root

The **root** is the entry point for graph-wide operations (traversal, depth, stats).

- `graph.root_key` may be `None` or may reference a key not in `nodes`
- `graph.root` returns `None` in either case
- Functions that accept `start_key` fall back to `root_key` when `start_key` is not provided
- A missing or invalid root is not an error — it produces empty/default results

## Cycles

Cycles are **tolerated but not followed**.

- Real-world lockfiles rarely contain cycles, but Depsly does not assume perfect input
- Cycle detection: `has_cycle()` uses white/gray/black coloring to detect back-edges
- Traversal (DFS, BFS): visited set prevents revisiting — each node visited at most once
- Transitive deps: cycles do not cause the start node to appear in its own dep set
- Max depth: ancestor set detects back-edges; they contribute depth 0 (breaking the cycle without suppressing deeper paths through shared nodes)

## Shared Nodes

A **shared node** is a node referenced by multiple parents (diamond dependency pattern).

- Only one `PackageNode` instance exists per key
- Multiple parents hold references to the same object
- Traversal visits shared nodes once (via visited set)
- Max depth computes and memoizes the full subtree depth of shared nodes, reusing it for every parent that references them — this ensures correct max depth even in diamond patterns

## Depth

**Depth** is measured from a start node (default: root).

- Start node is depth 0
- Each dependency edge adds 1
- `max_depth()` returns the longest path from start to any leaf
- Returns -1 if the start node doesn't exist
- Cycle back-edges are treated as depth 0 (not followed)
- Shared nodes report their full subtree depth to every parent (memoized, not skipped after first visit)

## Missing Dependencies

A dependency edge may reference a key not present in the graph.

- Missing keys are recorded in `graph.missing_keys`
- No edge is created for a missing dependency
- Missing dependencies are not errors — they are expected during partial ingestion
