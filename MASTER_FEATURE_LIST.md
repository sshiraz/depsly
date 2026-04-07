# Features

This file tracks the current implemented feature set at a high level.

For the chronological history with commit IDs, see `docs/implemented_features_by_commit.md`.

## Implemented Core
- [x] Dependency graph builder
- [x] Graph traversal, cycle detection, and depth analysis
- [x] `package-lock.json` v2/v3 ingestion
- [x] Structural graph analysis via `GraphReport`
- [x] Deterministic project risk scoring

## Implemented Product Features
- [x] Installable CLI with `depsly analyze`
- [x] Human-readable risk reporting and score breakdowns
- [x] Blast radius ranking
- [x] `depsly simulate-remove` structural what-if analysis
- [x] JSON output for machine-readable analysis

## Planned / Not Yet Implemented
- [ ] History tracking
- [ ] Safety drift analysis
- [ ] Monitoring and alerts
- [ ] CI integration
