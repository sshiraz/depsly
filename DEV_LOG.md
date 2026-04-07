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
