# Depsly Master Planning Bundle

This document consolidates:
- Product Requirements Document (PRD)
- Technical Specification
- Codex Task Breakdown

It is intended to be the single source of truth for planning and execution.

---

# 1. PRD (Summary)

## Vision
Depsly is a deterministic dependency decision engine that helps engineers analyze, simulate, and optimize dependency graphs before making changes.

## Core Value
- What to change
- What happens if you change it
- Whether it is feasible

## Key Features
- Analyze dependency graphs
- Simulate removal
- Recommend actions
- Trace dependency origins

---

# 2. Technical Spec (Summary)

## Architecture
CLI → Core Engine → Graph + Analysis + Simulation + Recommendation

## Core Modules
- ingestion
- graph
- analyze
- simulate
- classify
- trace
- recommend
- scoring

## Principles
- deterministic
- local-first
- no LLM dependency in core
- reusable modules

---

# 3. Codex Task Plan (Execution Order)

1. Models
2. Reverse edges + depth map
3. Classification
4. Trace engine
5. Simulation refactor
6. Feasibility scoring
7. Recommendation engine
8. CLI: recommend
9. CLI: trace
10. Output improvements
11. Scoring versioning
12. Performance pass
13. Docs
14. simulate-replace design

---

# 4. Development Workflow

For each task:
- Read existing code first
- Extend, do not duplicate
- Implement minimal working version
- Add tests
- Update docs

---

# 5. North Star

User runs:

    depsly recommend package-lock.json

And immediately knows:
- what matters
- what to change
- what will happen

---

# 6. Notes

- Always include structural disclaimer for simulations
- Prefer clarity over complexity
- Optimize only after correctness
