# STEP_2_SIMULATE_REMOVE.md

## Depsly Step 2: `simulate_remove(package)` Implementation Instructions for Claude Code

You are working in the `depsly` repo.

Your task is to implement the first version of project-local dependency change simulation.

This feature should answer:

"If I remove a package from the current project graph, what changes?"

This is not full replacement modeling.
This is not package-manager mutation.
This is not writing changes back to a lockfile.

It is a deterministic structural simulation over the existing in-memory dependency graph.

## Why this feature matters

Depsly's differentiator is not just showing what is risky.
It is showing the impact of change.

This feature is the first concrete version of that:

* remove one package conceptually
* recompute graph-derived metrics
* show before/after differences

## Existing repo context

Before coding:

1. Read:

   * `CLAUDE.md`
   * `ARCHITECTURE.md`
   * `ROADMAP.md`
   * `core/graph.py`
   * `core/analyze.py`
   * any CLI entrypoint already added
   * `tests/test_graph.py`
   * `tests/test_analyze.py`

2. Respect repo rules:

   * deterministic only
   * no frontend work
   * no dashboards
   * no LLM logic
   * no external graph libraries
   * no over-abstraction

## Scope

Implement a minimal but useful simulation.

### Goal

Given a package key in the current graph, produce a report showing:

* what nodes are affected by removing it
* what the remaining reachable graph looks like from the root
* how key metrics change before vs after

### Important constraint

This first version should simulate logical removal from the dependency graph model.

It does not need to:

* rewrite manifests
* find replacement packages
* repair broken dependency chains
* solve package-manager semantics perfectly

## Definition of "remove" for v1

For simulation purposes, "remove package X" means:

1. Conceptually delete node X from the graph
2. Remove all edges to and from X
3. Recompute the graph reachable from the root
4. Treat any parts of the graph that become unreachable from the root as no longer part of the effective project graph

This is a project-level what-if analysis, not a lockfile mutation engine.

## Files you may modify

Prefer to limit changes to:

* `core/graph.py`
* `core/analyze.py`
* `tests/test_graph.py`
* `tests/test_analyze.py`
* the CLI entrypoint if needed to expose the simulation command

Only add a new file if it materially improves clarity. Prefer not to split into many files.

## Step 1: Add a way to build a pruned / simulated graph

Implement a helper that constructs a new in-memory graph view excluding a target package.

Possible function:

```python
def simulate_remove_package(
    graph: DependencyGraph,
    package_key: str,
) -> DependencyGraph:
```

### Required behavior

* If `package_key` does not exist in the graph:

  * return a graph identical in effective structure to the original, or raise a clear error if that fits existing style better
* Exclude the target node from the new graph
* Exclude edges to and from the target node
* Preserve the same root if still present
* After removal, only include nodes reachable from the root
* If the removed package is the root:

  * return an empty effective graph or a clear, documented outcome

### Important

Do not mutate the original graph in place.

## Step 2: Add a simulation result object

In `core/analyze.py`, add a dataclass such as:

```python
@dataclass
class RemovalSimulationReport:
    package_key: str
    package_found: bool
    affected_node_count: int
    removed_subgraph_node_count: int
    before_report: GraphReport
    after_report: GraphReport
    risk_delta: int | float | None
```

## Step 3: Add the simulation analysis function

Add a function like:

```python
def analyze_removal_impact(
    graph: DependencyGraph,
    package_key: str,
) -> RemovalSimulationReport:
```

This function should:

1. Compute `before_report = analyze_graph(graph)`
2. Build a simulated graph with the package removed
3. Compute `after_report = analyze_graph(simulated_graph)`
4. Compute impact summary fields

### Impact metrics to include

At minimum:

* before total nodes vs after total nodes
* before max depth vs after max depth
* before transitive dependency count vs after
* before unresolved dependencies vs after if relevant

### If scoring already exists

If the repo already has a project scoring function, include:

* before score
* after score
* score delta

If scoring is not yet separated cleanly, do not force it in this task.

## Step 4: Define affected nodes carefully

Recommended definition for v1:

the number of nodes that disappear from the root-reachable graph after the package is removed

So:

* compute reachable nodes before removal
* compute reachable nodes after removal
* impacted = nodes present before but absent after

## Step 5: Add CLI support

Add a command like:

```bash
depsly simulate-remove path/to/package-lock.json package-key
```

### Example output

```text
Simulating removal: eslint@9.39.4

Before:
- Total dependencies: 204
- Max depth: 9
- Transitive dependencies: 161

After:
- Total dependencies: 173
- Max depth: 7
- Transitive dependencies: 132

Impact:
- 31 packages removed from the reachable graph
- Max depth reduced by 2
- Transitive dependency count reduced by 29
```

Keep it plain, readable, and deterministic.

## Step 6: Tests

Add tests for:

1. Basic removal in a chain
2. Shared transitive removal
3. Nonexistent package
4. Remove root
5. Cycle safety
6. Before/after metrics

Use exact assertions where practical.

## Design notes

Do not try to simulate package-manager repair behavior.
Do not invent alternative dependency resolution.
Do not introduce a solver.

This is only:

* remove a node
* recompute reachable structure
* compare reports

## Output expectations

After implementation, provide:

1. list of changed files
2. explanation of removal semantics used
3. explanation of how impacted nodes are computed
4. summary of tests added
5. any limitations or assumptions still present

