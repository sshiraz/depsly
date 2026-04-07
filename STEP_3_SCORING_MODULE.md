# STEP_3_SCORING_MODULE.md

## Depsly Step 3: Extract Project Scoring into `core/scoring.py` for Claude Code

You are working in the `depsly` repo.

Your task is to extract and formalize the project-level scoring logic into a dedicated scoring module.

This is about making scoring:

* explicit
* explainable
* deterministic
* testable

It is about taking Depsly's current structural metrics and turning them into a clean, reviewable scoring system.

## Why this matters

The CLI now shows a project risk label and score.
Users will ask:

"Why is this project scored 53 and not 31?"

A dedicated scoring module makes the answer:

* visible in code
* stable across changes
* easy to test
* easier to trust

It also separates:

* structural analysis (`core/analyze.py`)
  from
* scoring policy (`core/scoring.py`)

## Existing repo context

Before coding:

1. Read:

   * `CLAUDE.md`
   * `ARCHITECTURE.md`
   * `ROADMAP.md`
   * `core/analyze.py`
   * the current CLI entrypoint and formatting logic
   * any current project scoring helpers
   * `tests/test_analyze.py`

2. Respect repo rules:

   * deterministic only
   * no LLM scoring
   * no external APIs
   * no speculative architecture
   * keep the change small and clean

## Goal

Move scoring policy into a dedicated module and make it structured.

### Core outcome

There should be one canonical place where project-level score is calculated.

This scoring should be based on the existing `GraphReport` metrics.

## Files you may modify

Prefer to limit changes to:

* `core/scoring.py` (new)
* `core/analyze.py` if needed only for integration
* the CLI entrypoint
* `tests/test_analyze.py`
* `tests/test_scoring.py` (new, recommended)

## Step 1: Create a scoring module

Add:

```text
core/scoring.py
```

This file should contain:

* thresholds
* weights / point additions
* risk label mapping
* score breakdown generation

## Step 2: Add structured scoring result types

Add dataclasses such as:

```python
@dataclass
class ScoreComponent:
    name: str
    points: int
    detail: str

@dataclass
class ProjectScore:
    score: int
    label: str
    components: list[ScoreComponent]
```

### Label mapping

Keep it simple and deterministic, for example:

* `0-29` -> `LOW`
* `30-59` -> `MODERATE`
* `60+` -> `HIGH`

## Step 3: Implement the main scoring function

Add a function like:

```python
def score_project(report: GraphReport) -> ProjectScore:
```

## Step 4: Use existing structural signals

Base scoring on existing `GraphReport` fields.

Recommended initial signals:

### 1. Depth risk

Use `report.max_depth`.

Example:

* depth >= 8 -> +20
* depth >= 5 -> +12
* depth >= 3 -> +6
* else +0

### 2. Concentration / centralization risk

Use top-package dominance signal already produced by the CLI or computed from report.

Example:

* top packages control >= 50% -> +20
* > = 30% -> +12
* > = 15% -> +6

### 3. Transitive exposure risk

Use `report.transitive_dependency_count`.

Example:

* > = 150 -> +15
* > = 75 -> +10
* > = 25 -> +5

### 4. Size risk

Use `report.total_nodes`.

Example:

* > = 200 -> +10
* > = 100 -> +6
* > = 50 -> +3

### 5. Unresolved dependency risk

Use `report.unresolved_dependency_count`.

Example:

* > 0 -> +10 or +15

The exact numbers are suggestions. The key is that scoring is explicit and components are separable.

## Step 5: Clamp and normalize score

Final score should:

* be an integer
* be clamped to `0..100`

## Step 6: Make score breakdown explainable

Each component should have a detail string.

Example:

* `Depth risk`, `+20`, `depth 9`
* `Transitive risk`, `+15`, `161 indirect dependencies`
* `Centralization risk`, `+8`, `top packages control 44% of graph`

This should be the source of truth for CLI output.

## Step 7: Update CLI to use `core/scoring.py`

Refactor the CLI so that:

* it calls `score_project(report)`
* it prints the returned label and components
* it does not keep ad hoc score logic in the CLI itself

## Step 8: Add tests

Recommended new file:

```text
tests/test_scoring.py
```

Add tests for:

1. Low-risk project
2. Moderate-risk project
3. High-risk project
4. Unresolved dependencies affecting score
5. Score clamping
6. Component presence
7. Label mapping boundaries

Use exact assertions.

## Output expectations

After implementation, provide:

1. changed file list
2. scoring thresholds and rationale
3. explanation of how breakdown is generated
4. summary of tests added
5. any assumptions or limitations

