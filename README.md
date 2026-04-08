# Depsly

Depsly is a dependency risk analysis tool for engineering teams evaluating and monitoring open source packages.

## Problem
Most dependency tools focus only on vulnerabilities or compliance, not real decision-making.

## What Depsly Does
- Builds dependency graphs
- Analyzes risk across direct + transitive deps
- Tracks safety drift over time
- Supports pre- and post-adoption workflows

## Install

With `pipx`:

```bash
pipx install .
```

If your default `pipx` Python is older than `3.11`, install with:

```bash
pipx install --python python3.11 .
```

After install:

```bash
depsly --help
```

## Docs
See DOCUMENTATION_INDEX.md
