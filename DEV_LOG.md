# Dev Log

## 2026-04-05
- Initialized docs system
- Added initial FastAPI + Vite project scaffold
- Added core dependency graph engine
- Added package-lock ingestion
- Added structural graph analysis and CLI entry point
- Added headline project risk scoring to CLI output

## 2026-04-06
- Expanded CLI reporting with score breakdowns, concentration, and suggested actions
- Added blast radius analysis and ranking
- Added `simulate-remove` structural what-if analysis
- Extracted scoring to `core/scoring.py`
- Added JSON output for `depsly analyze`

## 2026-04-07
- Added implemented feature history document with commit IDs
- Updated feature inventory to match shipped functionality
- Tightened removal-impact analysis to reuse computed affected nodes instead of repeated per-dependent traversal
- Added shared simulation API and deterministic trace engine
- Added recommendation engine with package ranking based on impact and feasibility
- Added discrete actionability and reason-confidence labels for recommendation UX

## 2026-04-08
- Added shipped `depsly recommend` CLI output with project header, summary, priority cues, contextual next steps, and scoring-version display
- Added shipped `depsly trace` CLI command for deterministic shortest-path inspection
- Improved human-readable `depsly analyze` output with direct/transitive blast-radius labeling and guidance to `recommend` and `trace`
- Updated packaging metadata and README for `pipx`/PyPI release preparation
- Reduced duplicate simulation work during recommendation generation by reusing precomputed impact data
