# Depsly Codex Task Breakdown (v4 — append-only, with Corpus & Intelligence Layer)

## Principles
- Deterministic core
- No duplicated logic
- Keep CLI thin
- Update tests with each meaningful change
- Do not rewrite working modules unless required
- Extend existing logic first
- Append new work; do not delete prior roadmap items

---

## ✅ Completed

### Task 0 — Repo inspection/alignment
Status: DONE

### Task 1 — Shared models
Status: DONE

### Task 2 — Reverse-edge + depth helpers
Status: DONE

### Task 3 — Classification
Status: DONE

### Task 4 — Trace engine
Status: DONE

### Task 5 — Simulation standardization
Status: DONE

### Task 6 — Feasibility scoring
Status: DONE

### Task 7 — Recommendation engine
Status: DONE

### Task 8 — `recommend` CLI command
Status: DONE

### Task 9 — `trace` CLI command
Status: DONE

### Task 10 — Improve analyze output with classification-aware insights
Status: DONE

---

## ⏭️ Existing Planned / Not Yet Implemented

### Task 11 — Add scoring version to output
Goal:
Expose scoring version string (for example `v1`) in recommendation and other scored outputs.

Files:
- `core/scoring.py`
- CLI output logic

Acceptance criteria:
- visible in `recommend` output
- easy to bump later
- no scoring behavior changes required

Status: DONE

---

### Task 12 — Performance pass for recommendations
Goal:
Avoid expensive repeated traversals if recommendation performance becomes poor on large graphs.

Files:
- `core/recommend.py`
- `core/graph.py`
- maybe `core/scoring.py`

Requirements:
- cache subtree sizes or removed sets where helpful
- reuse reverse edges
- reuse depth maps
- reuse fanout maps
- keep implementation readable

Acceptance criteria:
- no unnecessary repeated full-graph scans where avoidable
- deterministic outputs preserved
- existing tests still pass

Status: DONE

---

### Task 13 — Documentation updates
Goal:
Bring repo docs in sync with the shipped CLI.

Files:
- `README.md`
- `MASTER_FEATURE_LIST.md`
- `ROADMAP.md`
- `DEV_LOG.md`
- `DECISIONS.md`
- `ARCHITECTURE.md`
- `DOCUMENTATION_INDEX.md`

Requirements:
Document:
- new commands: `recommend`, `trace`
- classification / actionability / reason-confidence concepts
- structural-only disclaimer
- install via pipx / PyPI
- scoring version once implemented

Acceptance criteria:
- docs reflect actual shipped behavior
- no overclaiming of unimplemented features

Status: DONE

---

### Task 14 — Design note for `simulate-replace`
Goal:
Prepare a realistic replacement feature without overbuilding now.

Files:
- design note only, no heavy implementation unless requested

Requirements:
Write a short internal design note covering:
- command shape
- structural assumptions
- curated known replacements vs generic replacement
- heuristic preview vs real compare-lockfiles approach
- trust / disclaimer implications

Acceptance criteria:
- clear enough to implement later
- explicitly marks v1 as heuristic if applicable
- no speculative engine changes yet

Status: DONE

---

## 📦 New Phase: Corpus & Intelligence Layer

### Task 15 — Add normalized scan export
Goal:
Persist Depsly outputs in a structured, machine-readable format.

Files:
- `core/export.py` (new) or `core/formatters.py`
- CLI entrypoint

Requirements:
Add `--json` export support for:
- `depsly recommend <lockfile> --json`
- optionally `depsly analyze <lockfile> --json`

Output should include:
- project summary metrics
- top recommendations with all fields
- top blast-radius packages
- scoring version (if implemented)
- timestamp
- lockfile path / scan metadata

Acceptance criteria:
- deterministic field ordering
- stable schema
- no business logic in CLI formatting layer
- suitable for downstream ingestion

Tests:
- valid JSON
- schema shape snapshot
- deterministic ordering

---

### Task 16 — Build batch scan script
Goal:
Scan multiple repos and persist normalized outputs.

Files:
- `scripts/scan_repos.py`
- optionally `scripts/scan_single_repo.py`

Behavior:
- input: list of repo paths or a manifest file
- locate `package-lock.json`
- run analyze + recommend pipeline
- export results to JSON / JSONL

Acceptance criteria:
- skips missing lockfiles cleanly
- logs failures without aborting whole batch
- deterministic output paths
- supports re-runs

Tests:
- unit tests for path handling
- dry-run mode if practical

---

### Task 17 — Define repo metadata schema
Goal:
Attach contextual metadata to scanned repos.

Metadata fields:
- `industry`
- `company_size`
- `repo_type`
- `stack_tags`

Recommended controlled vocab:

industry:
- SaaS
- Developer Tooling
- Infrastructure/Cloud
- E-commerce
- Content/CMS
- Fintech
- Unknown

company_size:
- small OSS
- startup
- mid-size
- enterprise
- unknown

repo_type:
- app
- framework
- library
- cli
- monorepo

stack_tags:
- freeform list like `react`, `nextjs`, `vite`, `nestjs`, `typescript`

Acceptance criteria:
- fields optional
- no auto-detection required yet
- schema documented

---

### Task 18 — Add manual metadata registry
Goal:
Support manual tagging without premature automation.

Files:
- `data/repo_metadata.json`

Behavior:
- lookup repo → attach metadata if present
- fallback to `unknown`

Acceptance criteria:
- easy manual editing
- no network calls
- clean merge into exported scan records

Tests:
- metadata present
- metadata absent
- malformed metadata handling

---

### Task 19 — Add ecosystem enrichment layer
Goal:
Augment structural findings with package health signals.

Files:
- `core/enrich.py`
- `core/models.py`

Initial optional fields:
- `last_published_at`
- `days_since_last_release`
- `maintainer_count`
- `open_known_vulnerabilities_count`
- `fix_available`

Constraints:
- all fields optional / nullable
- no failure if unavailable
- no effect on core structural scoring yet

Acceptance criteria:
- structural engine still works with zero enrichment
- enrichment is additive only
- deterministic fallback when metadata unavailable

---

### Task 20 — Add npm metadata fetch
Goal:
Fetch basic package freshness / maintainer signals for top packages.

Files:
- `core/enrich.py`
- optional cache module

Behavior:
- enrich top N recommendation packages only at first
- fetch npm registry metadata
- populate publish recency and maintainer count
- cache locally

Acceptance criteria:
- resilient to network errors / rate limits
- deterministic fallback when metadata missing
- cacheable and testable

Tests:
- mocked network calls
- cache hit / miss
- null-field fallback

---

### Task 21 — Add vulnerability signal integration
Goal:
Attach unresolved vulnerability signals to top findings.

Files:
- `core/enrich.py`

Initial fields:
- `open_known_vulnerabilities_count`
- `fix_available`

Scope:
- enrich top recommendations only
- do not block scans if vulnerability source unavailable

Acceptance criteria:
- additive only
- explicit separation between structural score and enriched metadata
- no changes to core deterministic graph logic

---

### Task 22 — Add SQLite storage
Goal:
Move from ad hoc JSON exports to a queryable local corpus.

Files:
- `storage/sqlite.py`
- schema/init script

Tables:
- `repos`
- `scans`
- `package_findings`
- later `package_enrichment`

Acceptance criteria:
- insert scan results idempotently
- repo + scan relationships preserved
- simple local queries possible
- JSON export remains supported

---

### Task 23 — Add corpus analysis script
Goal:
Generate first cross-repo insights from stored scans.

Files:
- `scripts/analyze_corpus.py`

Outputs examples:
- most common high-impact packages
- most frequent `TRACE_UPSTREAM` packages
- average depth by repo type
- direct vs transitive recommendation patterns
- dev dependency impact patterns

Acceptance criteria:
- works from SQLite or JSON corpus
- produces plain text / markdown summaries
- deterministic sorting

---

## 🖥️ Future Phase: UI / Team Layer (Deferred)

### Task 24 — Thin demo UI
Goal:
Create a minimal presentation layer only after corpus and insights exist.

Scope:
- upload / paste repo
- project summary
- top recommendations
- trace details
- simulate-remove preview

Constraint:
- reuse existing engine
- no heavy auth/billing/dashboard work yet

---

### Task 25 — Compare-lockfiles / before-after analysis
Goal:
Add a higher-trust alternative or complement to `simulate-replace`.

Why:
- likely more trustworthy than heuristic replace simulation
- useful for real migration diffs

Constraint:
- design after corpus work clarifies demand

---

### Task 26 — `simulate-replace` implementation
Goal:
Implement replacement preview only after:
- corpus work
- recommendation validation
- design note from Task 14

Constraint:
- keep realistic trust framing
- likely start with curated/heuristic replacement profiles

---

## 🎯 Current Priority Order

1. Task 13 — docs update
2. Task 15 — normalized scan export
3. Task 16 — batch scan script
4. Task 17 — repo metadata schema
5. Task 18 — manual metadata registry
6. Task 19 — ecosystem enrichment layer
7. Task 20 — npm metadata fetch
8. Task 21 — vulnerability signal integration
9. Task 22 — SQLite storage
10. Task 23 — corpus analysis script
11. Task 11 — scoring version
12. Task 12 — performance pass
13. Task 14 — simulate-replace design note
14. Task 24+ — UI / compare / replace later

---

## 🧠 Key Rule for Codex

Treat current CLI + structural engine as stable baseline.

Do:
- extend via export, storage, enrichment, and corpus analysis
- keep structural logic usable even with zero external metadata
- keep metadata enrichment additive and optional
- prefer manual taxonomy before auto-classification

Do NOT:
- rewrite graph/scoring core unless required
- move UI ahead of corpus validation
- remove prior roadmap items

---

## 🏁 Current Goal

Build a high-quality corpus of real dependency graphs and enriched findings so Depsly can:
- validate and calibrate scoring
- discover recurring patterns across repos
- support future UI and enterprise reporting
- add richer signals like maintainer count, stale packages, and unresolved vulnerabilities
