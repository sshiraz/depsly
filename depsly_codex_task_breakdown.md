# Depsly Codex Task Breakdown (v2 — with Status)

## Principles
- Deterministic core
- No duplicated logic
- Keep CLI thin
- Test every change

---

## ✅ Completed

### Task 0 — Repo inspection/alignment
Status: DONE

### Task 1 — Shared models
- core/models.py
- RemoveSimulationResult, PackageClassification, TraceResult, Recommendation
Status: DONE

### Task 2 — Reverse-edge + depth helpers
- build_reverse_edges
- parent_counts
- shortest_depths_from_root
Status: DONE

### Task 3 — Classification
- classify_package / classify_all_packages
Status: DONE

### Task 4 — Trace engine
- core/trace.py
- deterministic shortest paths
Status: DONE

### Task 5 — Simulation standardization
- core/simulate.py
- single simulate_remove API
Status: DONE

### Task 6 — Feasibility scoring
- compute_feasibility_score
- tooling penalty added
Status: DONE

### Task 7 — Recommendation engine
- core/recommend.py
- impact * feasibility
- action types: REMOVE / TRACE_UPSTREAM / REVIEW / DEFER
- actionability + reason_confidence
Status: DONE

---

## 🚧 In Progress / Next

### Task 8 — `recommend` CLI command
Goal:
Expose recommendation engine via CLI

Command:
    depsly recommend <lockfile>

Output fields:
- package_key
- action
- actionability (HIGH/MEDIUM/LOW)
- reason_confidence (HIGH/MEDIUM/LOW)
- impact %
- classification summary
- rationale bullets

Acceptance:
- deterministic output
- stable ordering
- readable format
- CLI thin (no business logic)

Tests:
- CLI snapshot / integration
- ordering stability
- empty graph

Status: NEXT

---

### Task 9 — `trace` CLI command
Command:
    depsly trace <lockfile> <package>

Output:
- 1–3 shortest root→target paths
- deterministic ordering

Status: NEXT (after recommend CLI)

---

## 🔜 Upcoming

### Task 10 — Analyze output improvements
- label direct vs transitive in output
- suggest next commands (recommend/trace)

### Task 11 — Scoring version
- expose scoring version (e.g., v1)

### Task 12 — Performance pass
- cache subtree sizes
- reuse reverse edges / depth map

### Task 13 — Docs update
- README
- feature list
- CLI commands

### Task 14 — simulate-replace design note
- no implementation yet

---

## 🧠 Current Architecture

graph → classify → simulate → scoring → recommend → CLI

---

## 🎯 Current Goal

Ship:
    depsly recommend <lockfile>

and ensure output is:
- believable
- actionable
- non-noisy

---

## Notes

- scoring currently uses: impact * feasibility
- feasibility includes tooling penalty
- actionability is derived from feasibility
- reason_confidence reflects data completeness

Keep tuning minimal — prioritize real usage feedback.
