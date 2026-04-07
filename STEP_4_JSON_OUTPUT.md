# STEP_4_JSON_OUTPUT.md

## Depsly Step 4: Add `--json` Output Mode for Claude Code

You are working in the `depsly` repo.

Your task is to add a machine-readable JSON output mode to the CLI.

This should make Depsly useful for:

* automation
* scripting
* future API compatibility
* CI integration
* regression testing
* easy before/after simulation comparisons

This is simply a second output mode for the existing CLI.

## Existing repo context

Before coding:

1. Read:

   * `CLAUDE.md`
   * current CLI entrypoint
   * `core/analyze.py`
   * `core/scoring.py` if already implemented
   * any simulation module if already implemented

2. Respect repo rules:

   * deterministic only
   * do not add frameworks
   * keep output contract stable
   * do not remove existing human-readable output

## Goal

Add a `--json` mode to the CLI so that users can run commands like:

```bash
depsly analyze path/to/package-lock.json --json
```

and receive structured JSON instead of formatted terminal text.

## Files you may modify

Prefer to limit changes to:

* CLI entrypoint
* optionally a small serializer helper if needed
* tests for CLI behavior if the repo already tests CLI

Do not build a large serialization framework.

## Step 1: Decide the JSON contract

The JSON contract should be:

* stable
* explicit
* nested enough to be useful
* not overly verbose

Recommended shape:

```json
{
  "project": "frontend",
  "report": {
    "root_package_key": "frontend@0.0.0",
    "total_nodes": 204,
    "total_edges": 250,
    "max_depth": 9,
    "has_cycle": false,
    "direct_dependency_count": 14,
    "transitive_dependency_count": 161,
    "unresolved_dependency_count": 0,
    "leaf_package_count": 97,
    "top_packages_by_fanout": [["eslint@9.39.4", 34]],
    "top_packages_by_blast_radius": [["eslint@9.39.4", 89, 0.436]]
  },
  "score": {
    "score": 53,
    "label": "HIGH",
    "components": [
      {"name": "Depth risk", "points": 20, "detail": "depth 9"}
    ]
  },
  "summary": {
    "concentration_pct": 0.44,
    "summary_text": "Your project has a deep and moderately concentrated dependency structure."
  }
}
```

## Step 2: Add `--json` flag

In the analyze command, add a boolean flag:

* `--json`

### Required behavior

* default behavior remains human-readable CLI output
* when `--json` is passed, emit JSON only
* do not mix colored terminal output with JSON mode

## Step 3: Serialize dataclasses cleanly

If the repo uses dataclasses like `GraphReport`, `ProjectScore`, or simulation result dataclasses, serialize them cleanly.

Recommended:

* `dataclasses.asdict(...)` for dataclass objects
* normalize tuples to lists if needed for JSON compatibility

Do not write a giant custom serializer unless necessary.

## Step 4: Keep percentages consistent

If values like blast radius percentages are stored as fractional floats:

* return them as raw floats in JSON
* do not multiply by 100 in the JSON payload unless that is already the repo convention

## Step 5: Support future simulation output

If a simulation command already exists or will exist soon, design the serialization approach so that it can also support:

```bash
depsly simulate-remove ... --json
```

You do not need to fully implement simulation JSON now if the command does not exist yet.

## Step 6: Tests

Add tests for:

* plain output mode
* `--json` mode
* valid JSON emitted
* expected keys present
* no ANSI color codes in JSON mode

If full CLI tests do not exist, add focused unit tests for serializer helpers.

## Output expectations

After implementation, provide:

1. changed file list
2. JSON contract summary
3. explanation of how dataclasses are serialized
4. tests added
5. any limitations or future notes

