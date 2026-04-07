# Depsly Technical Specification

## 1. Purpose

This document defines the technical architecture, module boundaries, data models, algorithms, CLI behavior, and implementation guidelines for Depsly.

Depsly is a deterministic dependency decision engine for JavaScript/TypeScript ecosystems. It parses dependency lockfiles, builds dependency graphs, computes structural risk metrics, simulates graph changes, and recommends actions.

This spec is intentionally implementation-oriented and optimized for local-first CLI usage first, with future reuse by API and UI layers.

---

## 2. Technical Principles

### 2.1 Deterministic core
All graph building, scoring, simulation, ranking, and recommendation logic must be deterministic.

Given the same:
- lockfile input
- command arguments
- scoring version

the output must be identical.

### 2.2 Separation of concerns
Strict boundaries:
- ingestion: parse raw lockfiles into normalized data
- graph: construct and traverse dependency graph
- analysis: compute structural metrics
- simulation: compute what-if graph changes
- recommendation: prioritize candidate actions
- presentation: CLI/API formatting only

### 2.3 Local-first operation
The CLI must work entirely locally from user-provided dependency manifests. No source code upload or network dependency should be required for core graph features.

### 2.4 Reuse over duplication
Shared graph computations must live in reusable core modules. CLI, API, and future UI should consume the same engine.

### 2.5 Honest scope
Simulation is structural unless explicitly upgraded later. The tool must never imply build/runtime correctness unless actually validated.

---

## 3. Supported Inputs

## 3.1 Initial support
- `package-lock.json`

## 3.2 Future support
- `yarn.lock`
- `pnpm-lock.yaml`

## 3.3 Input modes
- CLI path to lockfile
- CLI path to repo root with lockfile auto-discovery
- Future API upload

---

## 4. System Architecture

```text
CLI / API / Future UI
        |
        v
  Application Layer
        |
        v
  Core Engine
    |- ingestion
    |- graph
    |- analysis
    |- simulation
    |- recommendation
        |
        v
  Output Formatting
```

### 4.1 Current desired repo shape

```text
depsly/
  cli.py
  api.py                    # optional API layer
  core/
    ingestion.py
    graph.py
    analyze.py
    simulate.py
    recommend.py
    classify.py
    trace.py
    models.py
    scoring.py
    formatters.py
  tests/
    test_ingestion.py
    test_graph.py
    test_analyze.py
    test_simulate.py
    test_recommend.py
    test_trace.py
```

---

## 5. Data Model

## 5.1 Normalized package record

Every ingested package should normalize into a common shape.

```python
@dataclass(frozen=True)
class PackageRecord:
    key: str                # e.g. "eslint@9.39.4"
    name: str               # e.g. "eslint"
    version: str            # e.g. "9.39.4"
    dependencies: tuple[str, ...]   # keys of child deps
    dev: bool | None = None
    optional: bool | None = None
```

## 5.2 Normalized dependency dataset

```python
@dataclass(frozen=True)
class NormalizedDependencyData:
    root_key: str | None
    packages: dict[str, PackageRecord]
```

## 5.3 Graph node

```python
@dataclass
class DependencyNode:
    key: str
    name: str
    version: str
    dependencies: list["DependencyNode"]
```

## 5.4 Graph container

```python
@dataclass
class DependencyGraph:
    root_key: str | None
    root: DependencyNode | None
    nodes: dict[str, DependencyNode]
    missing_keys: set[str]
```

---

## 6. Ingestion Layer

## 6.1 Responsibilities
- parse lockfile content
- normalize package identifiers
- produce `NormalizedDependencyData`
- avoid graph logic in this layer

## 6.2 `package-lock.json` ingestion rules
The parser must:
- support lockfileVersion 2 and 3 where practical
- build package keys as `name@version`
- identify the root package from `packages[""]` when present
- resolve node_modules paths to package names
- populate dependency edges deterministically

## 6.3 Error handling
Raise clear typed errors for:
- file not found
- invalid JSON
- unsupported lockfile structure
- empty package set

Suggested exception types:
- `IngestionError`
- `UnsupportedLockfileError`
- `MalformedLockfileError`

---

## 7. Graph Layer

## 7.1 Responsibilities
- construct graph from normalized data
- detect missing package references
- expose traversal helpers
- expose aggregate graph statistics

## 7.2 Required functions

### `build_graph(normalized: NormalizedDependencyData) -> DependencyGraph`
Build all nodes, wire edges, record unresolved dependency keys.

### `graph_stats(graph: DependencyGraph) -> dict[str, int | bool]`
Return:
- total_nodes
- total_edges
- max_depth
- has_cycle

### `collect_transitive_deps(graph: DependencyGraph) -> set[str]`
Return all reachable dependency keys from root, excluding root.

### `reachable_subgraph_keys(graph, package_key) -> set[str]`
Return the set of nodes structurally removed if the selected node and its reachable subtree are removed from the dependency graph perspective.

### `reverse_edges(graph) -> dict[str, set[str]]`
Needed for parent tracing and classification.

## 7.3 Determinism requirements
- sort by key whenever tie-breaking is needed
- never rely on dict insertion order alone for presented output
- traversal outputs that are displayed must be consistently ordered

---

## 8. Analysis Layer

## 8.1 Responsibilities
Compute deterministic structural metrics for the current graph.

## 8.2 `GraphReport`

```python
@dataclass(frozen=True)
class GraphReport:
    root_package_key: str | None
    total_nodes: int
    total_edges: int
    max_depth: int
    has_cycle: bool
    direct_dependency_count: int
    transitive_dependency_count: int
    unresolved_dependency_count: int
    leaf_package_count: int
    top_packages_by_fanout: list[tuple[str, int]]
```

## 8.3 `analyze_graph(graph, fanout_limit=10) -> GraphReport`
Must compute:
- direct dependency count from root only
- transitive dependency count excluding root
- leaf count where out-degree == 0
- top packages by direct fanout
- deterministic tie-breaks by key

## 8.4 Risk scoring

### 8.4.1 Goal
Produce a composite structural risk score for the graph or candidate package that is explainable and deterministic.

### 8.4.2 Initial graph-level components
- depth risk
- size risk
- centralization risk
- transitive ratio risk

### 8.4.3 Example graph-level formula
All component scores normalized to 0-100:

```text
graph_risk_score =
    0.30 * depth_risk +
    0.25 * size_risk +
    0.25 * centralization_risk +
    0.20 * transitive_ratio_risk
```

### 8.4.4 Package-level impact score
Used for recommendations and simulations:

```text
impact_score = reachable_removed_nodes / total_nodes
```

This should be preserved as a float in `[0, 1]` internally and displayed as percent externally.

---

## 9. Simulation Layer

## 9.1 Responsibilities
Model structural what-if changes to the graph.

## 9.2 First supported simulation
- remove package

## 9.3 `simulate_remove(graph, package_key) -> RemoveSimulationResult`

```python
@dataclass(frozen=True)
class RemoveSimulationResult:
    package_key: str
    removed_keys: tuple[str, ...]
    removed_count: int
    total_nodes_before: int
    total_nodes_after: int
    percent_removed: float
    impacted_packages: tuple[str, ...]
    disclaimer: str
```

## 9.4 Behavior
- determine reachable subtree from selected package
- compute nodes removed
- compute new graph size
- compute impacted packages as direct reachable children or parent-linked impacts depending on chosen semantics
- output clear structural disclaimer

## 9.5 Output disclaimer
Always include text equivalent to:

> Structural simulation only. Does not guarantee install, build, or runtime correctness.

## 9.6 Future simulation types
- replace package
- multi-action plan
- compare scenarios

---

## 10. Classification Layer

## 10.1 Purpose
Make recommendations realistic by distinguishing packages users can directly act on from those that are mainly downstream artifacts.

## 10.2 `PackageClassification`

```python
@dataclass(frozen=True)
class PackageClassification:
    package_key: str
    is_root: bool
    is_direct_dependency: bool
    is_transitive_dependency: bool
    is_dev_dependency: bool | None
    parent_count: int
    depth_from_root: int | None
```

## 10.3 Required logic
- direct if directly referenced from root
- transitive if reachable from root but not direct
- root if equal to `root_key`
- dev from manifest data if available
- depth from shortest path from root

---

## 11. Trace Layer

## 11.1 Purpose
Show why a transitive dependency exists.

## 11.2 `trace_package(graph, package_key) -> TraceResult`

```python
@dataclass(frozen=True)
class TraceResult:
    package_key: str
    paths: tuple[tuple[str, ...], ...]
```

## 11.3 Behavior
- return at least one path from root to target
- optionally return top N shortest unique paths
- deterministic ordering:
  - shortest paths first
  - lexicographic tie-break

---

## 12. Recommendation Layer

## 12.1 Purpose
Translate graph analysis + simulation into ranked next actions.

## 12.2 `Recommendation`

```python
@dataclass(frozen=True)
class Recommendation:
    package_key: str
    impact_score: float
    feasibility_score: float
    final_score: float
    classification: PackageClassification
    recommendation_type: str
    rationale: tuple[str, ...]
```

## 12.3 Candidate selection
Only recommend packages that are reachable from root and structurally meaningful.

Possible filters:
- exclude root itself initially
- include both direct and transitive packages
- later allow `--direct-only`

## 12.4 Feasibility scoring heuristic (V1)
Initial deterministic heuristic:

```text
start = 0.5

+0.25 if direct dependency
+0.15 if dev dependency
+0.10 if depth_from_root <= 1
-0.20 if parent_count > 3
-0.10 if depth_from_root >= 3
-0.15 if fanout rank is very high
```

Clamp to `[0, 1]`.

## 12.5 Final ranking formula

```text
final_score = impact_score * feasibility_score
```

Alternative weighted form later:

```text
final_score =
    0.65 * impact_score +
    0.35 * feasibility_score
```

V1 should favor simplicity and explainability.

## 12.6 Recommendation types
Initial enum:
- `REMOVE`
- `TRACE_UPSTREAM`
- `REVIEW`
- `DEFER`

Example heuristics:
- direct + high impact + decent feasibility -> `REMOVE`
- transitive + high impact + low feasibility -> `TRACE_UPSTREAM`
- direct tooling package with high graph share -> `REVIEW`
- tiny impact -> `DEFER`

## 12.7 Required command
`depsly recommend <lockfile>`

Output should include:
- package
- impact
- feasibility
- type/classification
- concise rationale

---

## 13. CLI Specification

## 13.1 CLI goals
- fast local usage
- clean commands
- human-readable output
- stable text layout

## 13.2 Commands

### Analyze
```bash
depsly analyze path/to/package-lock.json
```

Outputs:
- graph summary
- risk score
- key structural risks
- most connected packages
- highest blast radius packages

### Simulate remove
```bash
depsly simulate-remove path/to/package-lock.json package@version
```

Outputs:
- removed node count
- new total
- percent removed
- impacted package list
- disclaimer

### Recommend
```bash
depsly recommend path/to/package-lock.json
```

Outputs:
- ranked top recommendations
- impact + feasibility + rationale

### Trace
```bash
depsly trace path/to/package-lock.json package@version
```

Outputs:
- one or more root-to-target paths

## 13.3 Output formatting rules
- stable section order
- stable sorting
- percentages displayed consistently
- counts comma-formatted where useful
- deterministic truncation rules for long lists

---

## 14. API Layer (Future-Compatible)

The core engine should be reusable by an API without duplicating logic.

Possible future endpoints:
- `POST /analyze`
- `POST /simulate/remove`
- `POST /recommend`
- `POST /trace`

The API must remain a thin wrapper around core modules.

---

## 15. Error Handling

## 15.1 CLI error rules
- non-zero exit on failure
- human-readable message
- no stack trace by default unless debug flag is present

## 15.2 Example failures
- missing lockfile
- invalid JSON
- package key not found
- unsupported format

---

## 16. Testing Requirements

## 16.1 Core testing principles
- all core logic testable without CLI
- no network dependency
- deterministic expected outputs

## 16.2 Required test coverage

### Ingestion
- valid lockfile parsing
- malformed JSON
- missing package structures

### Graph
- node/edge counts
- cycle handling
- missing dependency recording

### Analysis
- max depth
- fanout ranking
- direct/transitive counts
- deterministic tie handling

### Simulation
- remove reachable subtree
- counts before/after
- deterministic impacted list

### Recommendation
- stable ranking
- feasibility score bounds
- direct vs transitive classification effect

### Trace
- shortest path correctness
- deterministic path ordering

---

## 17. Performance Guidelines

## 17.1 Avoid repeated traversals
Use memoization for:
- reachable subtree computations
- depth lookup
- reverse edge derivation if reused often

## 17.2 Complexity expectations
For typical operations:
- graph build: O(V + E)
- graph stats: O(V + E)
- reachable subtree from one node: O(V + E) worst case
- recommendations over all nodes: optimize carefully, since naive repeated subtree traversal can drift toward O(V * (V + E))

## 17.3 Optimization plan
If recommendation performance becomes an issue:
- cache subtree sizes
- precompute reverse edges
- precompute shortest depth per node

---

## 18. Versioning

## 18.1 Scoring version
All scored output should expose a scoring version string.

Example:
```text
Scoring version: v1
```

## 18.2 Behavior versioning
If formulas materially change:
- increment scoring version
- preserve tests for prior behavior where needed
- note changes in changelog/dev log

---

## 19. Future Extensions

Planned but not required for current CLI-first milestone:
- `simulate-replace`
- multi-step optimization plans
- web UI
- CI integration
- historical trend tracking
- lockfile diff analysis
- import-usage-aware feasibility

---

## 20. Definition of Done by Milestone

## Milestone A
- analyze works robustly
- simulate-remove works robustly
- deterministic tests pass

## Milestone B
- recommend command implemented
- classification implemented
- trace implemented
- recommendation tests pass

## Milestone C
- replace simulation
- richer rationale output
- API wrapper

---

## 21. Final Technical Goal

A user should be able to run:

```bash
depsly recommend package-lock.json
```

and receive a deterministic, explainable answer to:

- what dependency matters most
- what happens structurally if it is removed
- whether it is realistically actionable
