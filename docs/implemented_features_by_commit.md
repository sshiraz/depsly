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

## 2026-04-07

### `a3714d8` Add classification and package scoring foundations
- Added shared core dataclasses for simulation, classification, tracing, and recommendations in `core/models.py`.
- Added reusable graph helpers for reverse-edge maps, parent counts, and shortest depths from root.
- Extended ingestion to preserve deterministic root dev-dependency metadata for downstream classification.
- Added `core/classify.py` for deterministic package classification using graph facts plus optional ingestion metadata.
- Extended `core/scoring.py` with package-level impact, feasibility, and combined package score computation while preserving existing project scoring behavior.
- Added tests covering shared models, graph helpers, classification, and package-level scoring.

### `507320b` Add trace engine and standardize simulation results
- Added `core/trace.py` with deterministic shortest-path tracing from root to a target package.
- Added `core/simulate.py` with `simulate_remove(graph, package_key)` as the shared structural simulation API.
- Standardized removal results through `RemoveSimulationResult`, including removed keys/counts, before/after totals, percent removed, impacted packages, disclaimer, and reusable simulated graph data.
- Refactored analysis, package impact scoring, and `simulate-remove` CLI handling to consume the shared simulation result instead of recomputing impact in multiple places.
- Added tests covering trace behavior, simulation result shape, CLI output consistency, and integration with existing analysis/scoring flows.

### `f7f1ae4` Add actionability and reason-confidence to recommendation engine
- Added `core/recommend.py` with deterministic recommendation ranking based on package classification, structural simulation, and package-level scoring.
- Extended recommendation data with discrete `actionability` labels (`HIGH`, `MEDIUM`, `LOW`) derived from feasibility scores.
- Added `reason_confidence` labels to express confidence in recommendation rationale from available structural and classification facts.
- Added a soft tooling-package feasibility penalty and tightened the `REVIEW` versus `DEFER` split to reduce noisy recommendations.
- Added focused tests for recommendation ranking, recommendation types, actionability labels, reason-confidence behavior, and tooling-aware feasibility scoring.

### `88a54c8` Add recommend CLI command
- Added the shipped `depsly recommend <lockfile>` CLI command.
- Kept CLI logic thin by delegating ranking and recommendation decisions to `core/recommend.py`.
- Added CLI coverage for deterministic ordering, output fields, limits, and empty-graph behavior.

### `386341d` Add trace CLI command and polish recommendation output
- Added the shipped `depsly trace <lockfile> <package>` CLI command for deterministic shortest-path tracing.
- Polished recommendation output with clearer header structure, contextual next steps, and improved `DEFER` wording.
- Added focused CLI test coverage for trace behavior and recommendation output refinements.

## 2026-04-08

### `4ab17ff` Improve analyze output and polish recommendation presentation
- Made human-readable `depsly analyze` output classification-aware by labeling blast-radius packages as direct or transitive.
- Added concrete next-step hints from `analyze` to `recommend` and `trace`, including a real transitive target when available.
- Surfaced scoring version metadata in recommendation output and upgraded recommendation presentation with project metadata, summary lines, stronger rationale wording, and priority cues.
- Added focused CLI coverage for the new analyze and recommendation presentation behavior.

### `a9e6464` Make Depsly installable via pipx
- Added `wheel` to build requirements so setuptools-based wheel builds work reliably in install workflows.
- Documented `pipx` installation and explicit Python 3.11 usage in the README.
- Improved local-install ergonomics without changing runtime CLI behavior.

### `1e121ed` Add README metadata for PyPI publishing
- Declared `README.md` as the package readme in `pyproject.toml`.
- Prepared the package for a populated PyPI long description and validated build artifacts with `twine check`.

### `7ff43fa` Replace README with product-focused release copy
- Replaced the minimal README with release-oriented product documentation.
- Documented the shipped CLI workflow around `analyze`, `recommend`, `trace`, and `simulate-remove`.
- Clarified the recommendation model, local-first positioning, install paths, and early release status.

### `4bbb734` Refine PyPI package metadata
- Updated package metadata to describe Depsly as a local-first dependency decision CLI for JS/TS projects.
- Added author metadata for PyPI publishing.

### `b48f1a0` Reduce duplicate simulation work in recommendation scoring
- Updated recommendation generation to reuse each package's existing structural simulation result when computing final scores.
- Extended package scoring helpers so callers can supply precomputed impact and feasibility values instead of recomputing them.
- Preserved existing ranking behavior while reducing duplicate simulation work on larger graphs.

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
- Package classification
- Package-level scoring
- Trace engine
- Standardized simulation results
- Recommendation engine
- Recommendation UX labels
- `recommend` CLI command
- `trace` CLI command
- Classification-aware analyze UX
- `pipx` / PyPI packaging metadata
