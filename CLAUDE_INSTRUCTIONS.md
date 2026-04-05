# DepSly Claude Code Instructions

## Overview
DepSly is a dependency intelligence tool for npm packages.

It evaluates:
- ecosystem blast radius
- maintainer concentration
- activity freshness
- advisory placeholder

## MVP Scope
- FastAPI backend
- React frontend
- Package lookup only

## Do NOT build
- auth, billing, dashboards
- monitoring infra
- GitHub Action
- database

## Endpoints

### GET /health
Returns:
- status: ok

### GET /analyze/{package}
Returns:
- package
- latest_version
- downloads_weekly
- maintainers_count
- last_updated
- years_since_update
- risk_score
- action
- factors
- summary
- suggested_alternatives

## Scoring

Weights:
- 35% blast radius
- 25% maintainer risk
- 20% activity risk
- 10% cve risk (placeholder)

## Action Logic

- single maintainer + stale > 2 years → REPLACE
- score ≥ 80 → REPLACE
- score ≥ 60 → REVIEW
- score ≥ 40 → MONITOR
- else → ACCEPT
