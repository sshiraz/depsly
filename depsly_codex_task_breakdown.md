# Depsly Codex Task Breakdown (v3 — current status)

## Principles
- Deterministic core
- No duplicated logic
- Keep CLI thin
- Test every change
- Do not claim unshipped features as complete

---

## ✅ Completed

### Task 0 — Repo inspection/alignment
Status: DONE

### Task 1 — Shared models
- `core/models.py`
- `RemoveSimulationResult`, `PackageClassification`, `TraceResult`, `Recommendation`
Status: DONE

### Task 2 — Reverse-edge + depth helpers
- `build_reverse_edges`
- `parent_counts`
- `shortest_depths_from_root`
Status: DONE

### Task 3 — Classification
- `classify_package`
- `classify_all_packages`
Status: DONE

### Task 4 — Trace engine
- `core/trace.py`
- deterministic shortest paths
Status: DONE

### Task 5 — Simulation standardization
- `core/simulate.py`
- single `simulate_remove` API
Status: DONE

### Task 6 — Feasibility scoring
- `compute_feasibility_score`
- tooling penalty added
Status: DONE

### Task 7 — Recommendation engine
- `core/recommend.py`
- `impact * feasibility`
- action types: `REMOVE` / `TRACE_UPSTREAM` / `REVIEW` / `DEFER`
- `actionability` + `reason_confidence`
Status: DONE

### Task 8 — `recommend` CLI command
Command:
    `depsly recommend <lockfile>`

Implemented output includes:
- project header
- scoring version
- summary block
- actionability
- reason confidence
- classification summary
- rationale bullets
- contextual next steps

Status: DONE

### Task 9 — `trace` CLI command
Command:
    `depsly trace <lockfile> <package>`

Output:
- 1–3 shortest root→target paths
- deterministic ordering

Status: DONE

### Task 10 — Analyze output improvements
- label direct vs transitive in blast-radius output
- suggest next commands (`recommend` / `trace`)

Status: DONE

### Task 11 — Scoring version
- expose scoring version (`v1`) in recommendation output

Status: DONE

### Task 13 — Docs update
- README updated for shipped CLI workflow
- feature list updated to reflect shipped commands
- commit-history doc updated with recent shipped work
- task breakdown synced to current implementation

Status: DONE

---

## 🔜 Remaining

### Task 12 — Performance pass
Goal:
Reduce repeated work in recommendation and simulation-heavy flows.

Candidates:
- cache subtree sizes
- reuse reverse-edge structures and depth maps more aggressively
- avoid repeated per-package simulation work where safe

Status: NEXT

### Task 14 — `simulate-replace` design note
Goal:
Write down the product and engine design for replacement simulation before implementation.

Status: OPEN

---

## 🧠 Current Architecture

`graph → classify → simulate → scoring → recommend → CLI`

---

## 🎯 Current Goal

Ship the current CLI cleanly, then decide whether to:
- optimize performance for larger lockfiles
- or design `simulate-replace`

---

## Notes

- scoring currently uses `impact * feasibility`
- feasibility includes tooling penalty
- actionability is derived from feasibility
- reason confidence reflects data completeness
- `simulate-replace` is not implemented
