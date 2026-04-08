# Simulate Replace Design Note

## Goal

Define a realistic first version of `simulate-replace` without overbuilding or pretending to model package-manager behavior exactly.

This note is intentionally design-only.
It does not require engine changes yet.

## Product shape

Proposed command:

```bash
depsly simulate-replace <lockfile> <package> --with <replacement>
```

Example:

```bash
depsly simulate-replace package-lock.json eslint@9.39.4 --with biome@1.9.4
```

Optional later flags:

```bash
--profile <replacement-profile>
--json
```

## Core question

The command should answer:

1. What structurally happens if package `A` is removed?
2. What structural assumptions are being made if package `B` is adopted instead?
3. How trustworthy is that preview?

## What replacement means

For v1, replacement should **not** mean:

- editing a lockfile
- resolving real npm package trees
- guaranteeing install success
- guaranteeing runtime compatibility

For v1, replacement should mean:

- remove package `A` structurally
- optionally add a heuristic replacement profile for package `B`
- recompute projected graph metrics under that assumption
- clearly disclose that the result is a preview, not a real dependency-resolution outcome

## Recommended v1 approach

Start with a **curated replacement profile** model, not a generic arbitrary-package model.

Reason:

- trust is higher when replacements are intentional and known
- generic package-name substitution implies precision the engine does not actually have
- curated profiles keep the first version deterministic and understandable

Example curated replacements:

- `eslint` -> `biome`
- `webpack` -> `vite`
- `moment` -> `dayjs`

Each curated replacement profile would describe expected structural behavior at a high level, for example:

- replacement usually reduces transitive depth
- replacement usually reduces tooling fanout
- replacement may require config migration

This is a better first product than pretending we can infer the true replacement subtree from package names alone.

## Two possible implementation modes

### Mode A: Heuristic preview

This is the recommended v1.

Behavior:

1. Run the existing `simulate_remove(package)` flow for the removed package.
2. Apply a small deterministic replacement profile for the target replacement.
3. Show projected metrics and confidence labels.

Output should be framed as:

- `Removed impact`
- `Projected replacement effect`
- `Net structural expectation`

Benefits:

- fast
- deterministic
- implementable with current architecture
- easy to explain

Limits:

- not resolver-accurate
- may under- or over-estimate replacement effects

### Mode B: Compare-lockfiles

This is the higher-trust future approach.

Behavior:

1. User provides a second lockfile representing the candidate replacement state.
2. Depsly compares:
   - current lockfile graph
   - proposed lockfile graph
3. Output is based on real structural deltas, not heuristics.

Example shape:

```bash
depsly compare-lockfiles before-package-lock.json after-package-lock.json
```

This is likely more trustworthy than heuristic replace simulation and may become the preferred long-term product.

## Trust model

`simulate-replace` must never present itself as exact dependency-resolution logic.

Required disclaimer for v1:

> Heuristic replacement preview only. Does not guarantee install, build, runtime, or exact lockfile resolution outcomes.

Recommended confidence levels:

- `HIGH`: compare-lockfiles mode with real before/after graphs
- `MEDIUM`: curated replacement profile with explicit assumptions
- `LOW`: generic replacement guess with no curated profile

## Recommendation for v1 scope

Do:

- implement only after current CLI/export priorities are done
- support a small curated replacement map first
- reuse `simulate_remove` as the base primitive
- keep output deterministic
- include a strong disclaimer

Do not:

- mutate lockfiles
- call package managers
- fetch registries during core simulation
- infer exact replacement dependency trees from package names alone

## Suggested output shape

```text
Simulating replacement:
- Remove: eslint@9.39.4
- Replace with: biome@1.9.4

Removal impact:
- 71 packages removed from the current reachable graph

Projected replacement effect:
- Expected lower tooling fanout
- Expected shallower transitive tree
- Config migration likely required

Net expectation:
- Structural complexity likely decreases
- Confidence: MEDIUM

Disclaimer:
- Heuristic replacement preview only. Does not guarantee install, build, runtime, or exact lockfile resolution outcomes.
```

## Architecture fit

If implemented later, likely module shape:

- `core/simulate.py`
  - keep `simulate_remove` unchanged
- `core/replace_profiles.py`
  - curated replacement profiles
- `core/recommend.py` or a new orchestration layer
  - combine remove result + replacement profile
- `cli.py`
  - thin command wrapper only

This keeps the current deterministic structure intact:

`graph -> simulate -> scoring/recommend -> CLI`

## Decision

If Depsly ships `simulate-replace`, the first acceptable version should be:

- curated
- deterministic
- explicitly heuristic

If higher trust is required, prefer a future `compare-lockfiles` flow over trying to fake full package-manager semantics.
