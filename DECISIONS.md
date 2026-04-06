# Decisions

## Keep docs lean
Reason: speed

## Prefer deterministic logic
Reason: cost + consistency

## Include devDependencies by default in ingestion
Reason: dev deps are part of the attack surface (supply chain risk). Controlled via `include_dev=False` for production-only analysis.

## name_to_key is lossy (P0 tech debt)
Reason: npm allows multiple versions of the same package. Current ingestion maps name -> single version, silently overwriting duplicates. Acceptable for v1 but must be fixed before multi-version resolution is needed. Future fix: `dict[str, list[str]]` with nearest-in-tree resolution.
