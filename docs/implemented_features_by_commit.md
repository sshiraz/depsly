# Implemented Features by Commit

This document tracks feature-bearing commits in the repository and summarizes what each one delivered.

It intentionally excludes documentation-only and workflow-only commits such as `a934af2`, `7d25a38`, and `8ecb250`.

## 2026-04-05

### `d431cdd` Initial project setup: FastAPI backend + Vite React frontend
- Bootstrapped the repository with a FastAPI backend.
- Added `/health` and `/analyze/{package}` API endpoints.
- Introduced an initial risk scoring model covering blast radius, maintainer, activity, and CVE placeholder signals.
- Scaffolded the Vite + React + TypeScript frontend.

### `8a9d6b2` Add core graph engine with model, builder, traversal, and tests
- Added the core dependency graph engine in `core/graph.py`.
- Introduced graph models, graph construction, DFS/BFS traversal, transitive dependency collection, cycle detection, and max-depth calculation.
- Established automated graph-engine test coverage.

### `61287fc` Add ingestion layer and origin doc
- Added `package-lock.json` v2/v3 ingestion in `core/ingestion.py`.
- Normalized lockfile data for graph construction.
- Supported scoped packages, dev dependencies, and transitive dependency resolution.

### `c50fd72` Fix ingestion review issues: root validation, dev deps flag, unresolved dep tracking
- Hardened ingestion with root-entry validation.
- Added `include_dev` control for dev dependency inclusion.
- Preserved unresolved dependency information in normalized output.

### `c3f0719` Add structural analysis layer with GraphReport
- Added `analyze_graph()` and the `GraphReport` analysis model.
- Implemented deterministic structural metrics including nodes, edges, depth, cycles, direct/transitive/unresolved counts, leaf count, and fan-out ranking.

### `b1eac76` Add CLI entry point for dependency analysis
- Added the `depsly analyze <lockfile>` command.
- Wired ingestion, graph-building, and analysis into an installable CLI workflow.

### `5000806` Add headline risk score, opinionated risk messages, and summary to CLI output
- Added a top-level project risk score to CLI output.
- Introduced opinionated risk messaging and an overall project summary.

### `ce4f612` Polish CLI output: colored risk labels, /100 scale, sharper insights
- Improved CLI readability with colored labels.
- Standardized risk presentation on a `/100` scale.
- Tightened the wording of CLI insights.

### `e399be4` Add score breakdown, restore size signal, use concentrated over centralized
- Added score component breakdowns to the CLI.
- Restored package-size influence in scoring.
- Reframed concentration language from "centralized" to "concentrated".

## 2026-04-06

### `21d7d72` Add dependency concentration standout metric block
- Added a dedicated standout metric block for dependency concentration in CLI output.

### `65dd9d7` Rebalance risk scoring and add transitive exposure insight
- Reweighted scoring components, especially centralization and size.
- Added transitive exposure interpretation to the CLI analysis.

### `68b5fdb` Add suggested actions section to CLI output
- Added a suggested-actions section to help users respond to analysis results.

### `b245891` Add blast radius: reverse edges, upward traversal, and ranking
- Added reverse-edge tracking to the graph model.
- Implemented blast-radius computation and package ranking by upstream impact.
- Extended `GraphReport` with blast-radius results.

### `8194b07` Add simulate-remove: structural what-if analysis for package removal
- Added structural removal simulation without mutating the original graph.
- Introduced `depsly simulate-remove` for what-if analysis of removing a package.
- Added before/after impact reporting for removal scenarios.

### `4fa2881` Improve simulate-remove UX: disclaimer, percentage, high-impact warning
- Improved `simulate-remove` output with clearer framing, percentage impact, and high-impact warnings.

### `a9ba4a1` Add top impacted packages to simulate-remove output
- Added ranked top-impacted direct dependents to removal simulation output.
- Surfaced which upstream packages lose the most subtree coverage after removal.

### `5b6cfdf` Improve depth explanation in simulate-remove output
- Added clearer depth-change explanations to removal simulation results.
- Distinguished between true depth reduction and cases where the removed package was not on the longest chain.

### `2e7bdf9` Extract project scoring to core/scoring.py
- Moved project scoring logic out of the CLI into `core/scoring.py`.
- Introduced typed scoring structures and a reusable `score_project()` flow.
- Made risk scoring independently testable.

### `be46d5e` Add --json flag to depsly analyze for machine-readable output
- Added `--json` output for `depsly analyze`.
- Exposed structured machine-readable output for project, risk, dependency, flag, fan-out, and blast-radius data.

### `7a57e8e` Add blast radius ranking to human-readable CLI output
- Added a human-readable "Highest blast radius packages" section to CLI output.
- Brought blast-radius analysis to parity between JSON and terminal output.

## Summary of Implemented Feature Areas

- Backend/API scaffold
- Frontend scaffold
- Dependency graph engine
- Lockfile ingestion
- Structural dependency analysis
- Installable CLI analysis workflow
- Risk scoring and score breakdowns
- Blast radius analysis
- Removal simulation / what-if analysis
- Human-readable and JSON reporting
