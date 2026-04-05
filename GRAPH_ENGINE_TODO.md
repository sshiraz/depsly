# GRAPH_ENGINE_TODO.md

## Status

Core graph engine (v1) is implemented and tested.

This document tracks **non-blocking improvements**, **known limitations**, and **next iterations**.
Nothing here should block current development.

---

# 🟢 Current Strengths

* Deterministic graph construction
* Single-instance nodes (no duplication)
* Cycle-safe traversal
* Correct handling of shared transitive dependencies
* Memoized depth calculation
* Clear test coverage across:

  * construction
  * traversal
  * cycles
  * stats

---

# 🟡 Non-Blocking Improvements (Next Iterations)

## 1. Input Validation Hardening

### Current State

`build_graph()` validates structure but assumes correct types in some fields.

### Improvements

* Validate:

  * `name` is `str`
  * `version` is `str`
  * each dependency key is `str`
* Fail fast with `GraphBuildError` on invalid types

### Why

Future ingestion (npm, pip, etc.) will introduce messy/untrusted data.

---

## 2. Root Validation / Behavior

### Current State

* `root_key` may be missing or not present in `nodes`
* `graph.root` silently returns `None`

### Options

* Option A: Validate root exists in nodes
* Option B: Explicitly document that missing root is allowed

### Decision (TBD)

Keep flexible for now, but document behavior clearly.

---

## 3. Dependency Deduplication Performance

### Current State

```python
if node not in self.dependencies:
```

* O(n) check per insertion

### Future Improvement

* Option A: Maintain `dependency_keys: set[str]`
* Option B: Deduplicate during graph build instead

### Why

Large graphs (10k+ nodes) will make this inefficient.

---

## 4. GraphStats Return Type

### Current State

```python
dict[str, int | bool]
```

### Future Improvement

* Replace with a dataclass:

```python
@dataclass
class GraphStats:
    total_nodes: int
    total_edges: int
    max_depth: int
    has_cycle: bool
```

### Why

* Better type safety
* Easier extension later

---

## 5. Missing Dependency Handling

### Current State

* Missing dependencies stored in `graph.missing_keys`

### Possible Improvements

* Track **which node referenced the missing dependency**
* Provide debug/reporting helpers

### Why

Important for:

* debugging ingestion
* user-facing error reporting

---

# 🟡 Test Improvements

## 1. Stronger Traversal Assertions

### Current State

```python
assert len(order) == 3
```

### Improvement

Assert exact node sets:

```python
assert set(order) == {"a@1.0.0", "b@1.0.0", "c@1.0.0"}
```

### Why

Prevents false positives

---

## 2. Additional Validation Tests

Add tests for:

* non-string `name`
* non-string `version`
* dependency list containing non-strings
* invalid `root` type

---

## 3. Replace sys.path Hack

### Current State

```python
sys.path.insert(...)
```

### Improvement Options

* use `PYTHONPATH`
* or install package locally
* or use pytest config

### Why

Cleaner test environment

---

## 4. Edge Case Tests

Add:

* empty graph + traversal
* graph with root not in nodes
* single-node graph
* very deep chain (stress test)

---

# 🔵 Future (Not Now)

These are intentionally **out of scope for v1**:

## Graph Enhancements

* reverse edges (dependents)
* weighted edges (risk propagation)
* subgraph extraction

## Performance

* large graph optimization
* caching across runs

## Analysis Layer (separate module)

* risk scoring
* vulnerability propagation
* license conflicts

## Ingestion Layer

* npm lockfile parsing
* pip requirements parsing
* normalization layer

---

# ⚠️ Philosophy

* Keep graph engine **minimal and correct**
* Avoid premature abstraction
* Optimize only when real data demands it
* Prefer clarity over cleverness

---

# ✅ Next Step

Proceed to:

👉 **Normalized ingestion layer (NOT package-manager specific yet)**

This will define the contract between:

* raw dependency data
* graph builder

---

# Owner Notes

This file should evolve as:

* real bugs are discovered
* performance bottlenecks appear
* ingestion complexity increases

Do NOT let this turn into a dumping ground for speculative ideas.

