# Depsly Codex Task Breakdown

## Instructions for Codex

This document breaks the Depsly roadmap into execution-ready tasks. Follow the repository's existing architectural constraints:
- deterministic core only
- do not duplicate logic
- keep CLI thin
- update tests with each meaningful change

Each task should be implemented in a small, reviewable unit. Prefer one task per commit.

---

## Task 0: Inspect and align with existing code

### Goal
Understand current repo state before adding new logic.

### Actions
- inspect `core/ingestion.py`
- inspect `core/graph.py`
- inspect `core/analyze.py`
- inspect current CLI entrypoint
- identify current dataclasses and helper functions
- do not rewrite existing working code

### Deliverable
Short implementation note:
- what files already exist
- what can be extended
- what new files are actually needed

---

## Task 1: Stabilize shared models

### Goal
Create or consolidate canonical shared dataclasses for simulation, classification, tracing, and recommendations.

### Files
- modify `core/models.py` if it exists
- otherwise create `core/models.py`

### Requirements
Add dataclasses for:
- `RemoveSimulationResult`
- `PackageClassification`
- `TraceResult`
- `Recommendation`

### Acceptance criteria
- no business logic in model definitions
- type hints present
- no duplication of already-existing structures

### Tests
- minimal import smoke test if needed

---

## Task 2: Build reverse-edge utilities

### Goal
Support parent tracing and classification.

### Files
- modify `core/graph.py`

### Requirements
Add:
- `build_reverse_edges(graph) -> dict[str, set[str]]`
- helper to compute parent counts
- helper to compute shortest depth from root to every reachable node

### Acceptance criteria
- deterministic outputs
- efficient reuse across modules

### Tests
Create/update tests covering:
- parent counts
- shortest depth correctness
- missing root behavior

---

## Task 3: Implement package classification

### Goal
Classify each package as direct, transitive, root, and dev where detectable.

### Files
- create `core/classify.py`
- possibly modify ingestion if dev metadata is not preserved yet

### Requirements
Implement:
- `classify_package(graph, package_key, normalized_data=None) -> PackageClassification`
- `classify_all_packages(graph, normalized_data=None) -> dict[str, PackageClassification]`

### Logic
- `is_root`: package key equals root
- `is_direct_dependency`: present directly under root dependencies
- `is_transitive_dependency`: reachable from root and not direct/root
- `is_dev_dependency`: use normalized manifest flag when available
- `parent_count`: derived from reverse edges
- `depth_from_root`: derived from shortest-depth map

### Acceptance criteria
- direct and transitive classification correct
- deterministic
- no CLI formatting here

### Tests
- direct dependency case
- transitive dependency case
- root case
- missing package case
- dev dependency case if supported

---

## Task 4: Implement trace engine

### Goal
Explain why a transitive package exists.

### Files
- create `core/trace.py`

### Requirements
Implement:
- `trace_package(graph, package_key, max_paths=3) -> TraceResult`

### Behavior
- find one or more shortest root-to-target paths
- order by:
  1. shortest path length
  2. lexicographic tie-break
- return tuple-of-tuples for deterministic immutability

### Acceptance criteria
- works for direct packages
- works for transitive packages
- returns clear path structure
- deterministic path ordering

### Tests
- shortest path case
- multiple path case
- unreachable package case
- direct dependency path case

---

## Task 5: Refactor simulation result into shared model

### Goal
Standardize `simulate-remove` return type and keep simulation logic reusable by recommendations.

### Files
- create `core/simulate.py` if not already present
- or modify existing simulation module
- adjust CLI to consume shared result object

### Requirements
Implement or refactor:
- `simulate_remove(graph, package_key) -> RemoveSimulationResult`

### Output fields
- package key
- removed keys
- removed count
- before/after totals
- percent removed
- impacted packages
- disclaimer

### Acceptance criteria
- current CLI behavior preserved or improved
- ordering deterministic
- suitable for programmatic reuse

### Tests
- simulation count correctness
- before/after totals
- percent calculation
- stable impacted list order
- package-not-found error

---

## Task 6: Implement feasibility scoring

### Goal
Create a deterministic heuristic that estimates how actionable a package is.

### Files
- create `core/scoring.py`

### Requirements
Implement:
- `compute_feasibility_score(graph, package_key, classification, fanout_map, depth_map) -> float`

### V1 heuristic
Start from `0.5` then:
- `+0.25` if direct dependency
- `+0.15` if dev dependency
- `+0.10` if depth <= 1
- `-0.20` if parent_count > 3
- `-0.10` if depth >= 3
- `-0.15` if fanout is very high

Clamp to `[0.0, 1.0]`.

### Acceptance criteria
- deterministic
- simple
- explainable
- easy to tune later

### Tests
- score stays in bounds
- direct dependency gets better score than similar deep transitive one
- heavily shared transitive package gets penalized

---

## Task 7: Implement recommendation engine

### Goal
Rank packages by impact and feasibility.

### Files
- create `core/recommend.py`

### Requirements
Implement:
- `recommend_packages(graph, normalized_data=None, limit=10) -> list[Recommendation]`

### Algorithm
For each reachable non-root package:
1. run `simulate_remove`
2. compute `impact_score = removed_count / total_nodes_before`
3. compute classification
4. compute feasibility
5. compute `final_score = impact_score * feasibility_score`
6. assign `recommendation_type`
7. generate short rationales

### Recommendation type heuristics
- direct + high impact + feasibility >= moderate -> `REMOVE`
- transitive + high impact + low feasibility -> `TRACE_UPSTREAM`
- direct + high impact but build-tool style -> `REVIEW`
- low impact -> `DEFER`

### Acceptance criteria
- result list sorted descending by final score
- stable tie-break by package key
- rationale strings concise and deterministic

### Tests
- ranking deterministic
- direct high-impact package ranks above similar low-feasibility transitive package
- empty graph handled
- limit respected

---

## Task 8: Add `recommend` CLI command

### Goal
Expose recommendation engine to end users.

### Files
- modify CLI entrypoint only
- add formatting helpers if needed in `core/formatters.py` or CLI module

### Command
```bash
depsly recommend path/to/package-lock.json
```

### Output requirements
For top N recommendations show:
- package key
- impact percent
- feasibility label
- classification summary
- recommendation type
- 1-2 rationale bullets

### Acceptance criteria
- command works end-to-end
- formatting is readable
- CLI remains thin and delegates to core logic

### Tests
- CLI integration test or snapshot test if repo already has CLI testing pattern
- stable output ordering

---

## Task 9: Add `trace` CLI command

### Goal
Expose path tracing to end users.

### Files
- modify CLI entrypoint
- reuse `core/trace.py`

### Command
```bash
depsly trace path/to/package-lock.json package@version
```

### Output requirements
- show 1 to 3 root-to-target paths
- stable formatting
- clear message when package is not reachable from root

### Acceptance criteria
- direct dependency trace works
- transitive dependency trace works
- multiple paths displayed deterministically

### Tests
- CLI command test
- package-not-found case

---

## Task 10: Improve analyze output with classification-aware insights

### Goal
Make analysis more actionable without changing its core purpose.

### Files
- CLI formatter and/or analysis formatter

### Requirements
Where applicable:
- clearly label whether highest blast-radius packages are direct or transitive
- avoid implying transitive packages are directly removable
- optionally show a hint:
  - "Use `depsly trace <package>` to see why this package exists."
  - "Use `depsly recommend` for prioritized actions."

### Acceptance criteria
- more realistic wording
- no major change to underlying analysis calculations

---

## Task 11: Add scoring version to output

### Goal
Prepare for future formula evolution without losing trust.

### Files
- `core/scoring.py`
- CLI output logic

### Requirements
Expose scoring version string, e.g. `v1`.

### Acceptance criteria
- visible in `recommend` output
- easy to bump later

---

## Task 12: Performance pass for recommendations

### Goal
Avoid expensive repeated traversals if recommendation performance becomes poor on large graphs.

### Files
- `core/recommend.py`
- `core/graph.py`
- maybe `core/scoring.py`

### Requirements
Profile or reason through repeated work and cache:
- subtree sizes or removed sets where helpful
- reverse edges
- depth map
- fanout map

### Acceptance criteria
- no unnecessary repeated full-graph scans where avoidable
- implementation remains readable

### Tests
- existing tests still pass
- optional benchmark harness if repo already uses one

---

## Task 13: Documentation updates

### Goal
Keep repo docs aligned with new capabilities.

### Files
- `README.md`
- `MASTER_FEATURE_LIST.md`
- `ROADMAP.md`
- `DEV_LOG.md`
- `DECISIONS.md`
- possibly `ARCHITECTURE.md`

### Requirements
Document:
- new commands: `recommend`, `trace`
- classification and feasibility concepts
- structural-only disclaimer
- scoring version

### Acceptance criteria
- docs reflect actual shipped behavior
- no mention of unimplemented features as if complete

---

## Task 14: Optional next milestone planning for `simulate-replace`

### Goal
Prepare the next major feature without overbuilding now.

### Files
- no heavy implementation unless requested
- create design note only

### Requirements
Write a short internal design note covering:
- command shape
- structural assumptions
- whether replacement graph is heuristic or resolved from alternate lockfile

### Acceptance criteria
- clear enough to implement later
- no speculative code unless requested

---

## Suggested commit order

1. shared models
2. reverse-edge utilities
3. classification
4. trace engine
5. simulation refactor
6. feasibility scoring
7. recommendation engine
8. `recommend` CLI
9. `trace` CLI
10. analyze output improvements
11. scoring version
12. perf pass
13. docs
14. replace design note

---

## Final instruction to Codex

Do not rewrite working graph or analysis code unless needed.
Prefer extending the current deterministic engine.
Keep logic in core modules, not in CLI formatting.
Every task must include or update tests.
