# Depsly – Blast Radius Implementation (Safe, Minimal Scope)

You are working in the `depsly` repo.

Your task is to implement **project-local blast radius** as a new analysis capability.

⚠️ IMPORTANT CONSTRAINTS:

* Do NOT modify ingestion
* Do NOT modify simulate-remove logic
* Do NOT change scoring behavior
* Do NOT refactor existing graph traversal logic
* Keep changes minimal and isolated

This is an additive feature only.

---

# 1. Definition of Blast Radius (Use This Exactly)

Blast radius for a package is:

> The number of nodes in the current project graph that depend on this package, directly or indirectly.

Equivalent interpretation:

> If this package is removed, how many nodes upstream are affected?

This is an **upstream traversal problem** (dependents), not downstream.

---

# 2. Step 1 – Add Reverse Edges to Graph

File: `core/graph.py`

## Goal

Enable traversal from a node → its dependents.

## Changes

### In `PackageNode`, add:

```python
self.dependents: list[PackageNode] = []
```

### Add method:

```python
def add_dependent(self, node: "PackageNode") -> None:
    if node not in self.dependents:
        self.dependents.append(node)
```

### Update graph construction

Wherever you currently do:

```python
node.add_dependency(dep_node)
```

Also add:

```python
dep_node.add_dependent(node)
```

---

## Constraints

* Do NOT remove or change existing dependency logic
* Do NOT change node identity or keys
* Do NOT introduce sets unless already used elsewhere
* Maintain deterministic ordering

---

# 3. Step 2 – Implement Blast Radius Computation

File: `core/analyze.py`

Add:

```python
def compute_blast_radius(
    graph: DependencyGraph,
    package_key: str,
    *,
    include_self: bool = False,
) -> tuple[int, float]:
```

---

## Behavior

* If package does not exist:

  * return (0, 0.0)

* Traverse upward using `.dependents`

* Use BFS or DFS

* Must:

  * avoid infinite loops (cycle-safe)
  * deduplicate visited nodes

---

## Algorithm

1. Get start node
2. Initialize:

   * visited = set()
   * stack or queue = [start_node]
3. Traverse via `.dependents`
4. Add nodes to visited
5. Stop when no more nodes

---

## Counting

* If `include_self=False`, exclude starting node
* affected_count = len(visited) (minus self if excluded)
* total_nodes = len(graph.nodes)

---

## Percentage

```python
affected_pct = affected_count / total_nodes
```

Return float in range [0.0, 1.0]

---

# 4. Step 3 – Rank Packages by Blast Radius

Add:

```python
def top_packages_by_blast_radius(
    graph: DependencyGraph,
    *,
    limit: int = 10,
    exclude_root: bool = True,
) -> list[tuple[str, int, float]]:
```

---

## Behavior

* Compute blast radius for all nodes
* Exclude root by default
* Sort by:

  1. affected_count DESC
  2. package_key ASC (stable tie-breaker)

---

## Edge cases

* limit = 0 → return []
* limit < 0 → raise ValueError

---

# 5. Step 4 – Integrate into GraphReport

Extend your existing `GraphReport`:

```python
top_packages_by_blast_radius: list[tuple[str, int, float]]
```

Update `analyze_graph()`:

* call `top_packages_by_blast_radius(...)`
* store results

---

# 6. Step 5 – CLI Output (Minimal)

In `depsly analyze` output, add a new section:

```text
Highest blast radius packages:

1. eslint@9.39.4 → affects 113 packages (55%)
2. webpack@5.x → affects 89 packages (43%)
```

---

## Formatting

* Convert percentage to whole percent (multiply by 100, round)
* Keep consistent with existing CLI style
* Do NOT add colors or complex formatting

---

# 7. Step 6 – JSON Output

Ensure blast radius appears in JSON:

```json
"top_packages_by_blast_radius": [
  ["eslint@9.39.4", 113, 0.55]
]
```

---

# 8. Step 7 – Tests

File: `tests/test_analyze.py`

Add:

## 1. Simple chain

A → B → C

* C blast radius = 2 (B, A)

## 2. Shared dependency

A → C
B → C

* C blast radius = 2 (A, B)

## 3. Root exclusion

* root not in results by default

## 4. Nonexistent package

* returns (0, 0.0)

## 5. Cycle safety

* no infinite loop

## 6. Deterministic ranking

* ties sorted by key

---

# 9. Step 8 – DO NOT DO THESE

Do NOT:

* reuse simulate-remove internally
* modify ingestion
* add scoring based on blast radius
* build UI
* introduce caching or optimization yet

---

# 10. Success Criteria

This task is complete when:

* graph supports dependents
* blast radius computed correctly
* rankings are deterministic
* CLI shows top packages
* JSON includes results
* all tests pass
* no regressions in existing features

---

# Final Note

Keep this implementation simple and correct.

This is a foundational feature that will later power:

* critical package ranking
* remediation planning
* dependency optimization

Do not over-engineer it.

