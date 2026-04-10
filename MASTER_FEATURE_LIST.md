# Features

This file tracks the current implemented feature set at a high level.

For the chronological history with commit IDs, see `docs/implemented_features_by_commit.md`.

## Implemented Core
- [x] Dependency graph builder
- [x] Graph traversal, cycle detection, and depth analysis
- [x] Reverse-edge utilities and parent counts
- [x] Shortest-depth computation from root
- [x] `package-lock.json` v2/v3 ingestion
- [x] Structural graph analysis via `GraphReport`
- [x] Deterministic project risk scoring
- [x] Shared core models for simulation, classification, tracing, and recommendations
- [x] Package classification engine
- [x] Package-level scoring primitives
- [x] Trace engine for deterministic shortest root-to-target paths
- [x] Standardized structural simulation result API
- [x] Recommendation engine with deterministic ranking
- [x] Discrete actionability and reason-confidence labels for recommendations
- [x] Reduced duplicate simulation work in recommendation scoring

## Implemented Product Features
- [x] Installable CLI with `depsly analyze`
- [x] Installable CLI with `depsly recommend`
- [x] Installable CLI with `depsly trace`
- [x] Human-readable risk reporting and score breakdowns
- [x] Classification-aware analyze output with next-step guidance
- [x] Blast radius ranking
- [x] `depsly simulate-remove` structural what-if analysis
- [x] JSON output for machine-readable analysis
- [x] Recommendation output with scoring version, actionability, and reason-confidence labels
- [x] `pipx`-ready package metadata and published-package README metadata

## Planned / Not Yet Implemented
- [ ] `simulate-replace` command / implementation
- [ ] History tracking
- [ ] Safety drift analysis
- [ ] Monitoring and alerts
- [ ] CI integration
