# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is DepSly?

Dependency risk analysis tool for npm packages. Scores packages on blast radius, maintainer concentration, activity freshness, and CVE risk (placeholder), then recommends an action: ACCEPT, MONITOR, REVIEW, or REPLACE. Goal: provide clear decisions, not just analysis.

## MVP Scope

- FastAPI backend (Python 3.11) — `api.py`
- React frontend (Vite + TypeScript) — `frontend/`
- Package lookup only

**Do NOT build:** auth, billing, dashboards, monitoring infra, GitHub Actions, database.

## Commands

### Backend
```bash
source venv/bin/activate
uvicorn api:app --reload          # runs on :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                       # runs on :5173
npm run build
npm run lint
```

## API Endpoints

- `GET /health` — returns `{"status": "ok"}`
- `GET /analyze/{package}` — returns risk score, action, factors, summary, suggested_alternatives

## Architecture

Backend fetches live from npm registry (`registry.npmjs.org`) and npm downloads API. No database — all data computed on the fly. Frontend calls backend at `localhost:8000`. CORS configured for `localhost:5173`.

Future components (not yet built): ingestion, graph builder, storage, CLI.

## Risk Scoring

Weighted formula (0-100):
- 35% blast radius (weekly download tiers)
- 25% maintainer risk (fewer maintainers = higher risk)
- 20% activity risk (years since last update)
- 10% CVE risk (placeholder, always 0)

## Action Logic

- Single maintainer + stale > 2 years → REPLACE
- Score >= 80 → REPLACE
- Score >= 60 → REVIEW
- Score >= 40 → MONITOR
- Else → ACCEPT

## Design Decisions

- Keep docs lean (speed over completeness)
- Prefer deterministic logic (cost + consistency — no LLM calls in scoring)
- Avoid duplication; check existing code first
- Minimize dependencies; build incrementally
- Validate inputs, do not execute external code, limit recursion

## Workflow

1. Read docs
2. Propose plan
3. Implement incrementally
4. Update docs
