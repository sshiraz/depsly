# 🚀 Depsly

**Depsly is a local-first dependency decision CLI for JavaScript/TypeScript projects.**

It helps you answer:

- What dependencies actually matter?
- What should I review first?
- Why is this transitive package even here?
- What happens if I remove something?

---

## 🧠 Why Depsly

Most dependency tools focus on:
- vulnerabilities
- compliance
- audit reports

Depsly focuses on:

> **Decision-making**

It combines:
- dependency graph analysis  
- structural impact simulation  
- feasibility-aware recommendations  
- saved scan history and comparison  

So you can decide **where to spend your time**.

---

## ✨ What Depsly Does

- Builds a full dependency graph from `package-lock.json`
- Analyzes structural risk (depth, fanout, transitive exposure)
- Ranks dependencies by **impact × actionability**
- Explains why transitive dependencies exist
- Simulates structural impact of removing packages
- Exports normalized recommendation scans as JSON
- Saves scans locally for history and comparison
- Generates an interactive HTML dependency explorer with tree, path, and graph views
- Runs entirely **locally** (no code upload required)

---

## ⚡ Install

### Recommended (pipx)

```bash
pipx install depsly
```

If needed:

```bash
pipx install --python python3.11 depsly
```

---

### Alternative (pip)

```bash
pip install depsly
```

---

## 🚀 Quick Start

### Analyze your dependency graph

```bash
depsly analyze package-lock.json
```

JSON export:

```bash
depsly analyze package-lock.json --json
```

---

### Get prioritized recommendations

```bash
depsly recommend package-lock.json
```

JSON export:

```bash
depsly recommend package-lock.json --json
```

---

### Trace why a package exists

```bash
depsly trace package-lock.json @babel/core@7.29.0
```

JSON export:

```bash
depsly trace package-lock.json @babel/core@7.29.0 --json
```

---

### Preview structural impact of removal

```bash
depsly simulate-remove package-lock.json eslint@9.39.4
```

JSON export:

```bash
depsly simulate-remove package-lock.json eslint@9.39.4 --json
```

---

### Save and compare scans over time

```bash
depsly save-scan package-lock.json
depsly list-scans --project frontend
depsly compare-scans ~/.depsly/scans/frontend-2026-04-11T10-15-43Z.json ~/.depsly/scans/frontend-2026-04-12T09-20-00Z.json
```

---

### Open the dependency graph in your browser

```bash
depsly graph-html package-lock.json
```

The HTML report now opens in an Explorer-first surface:

- `Explorer` view for a readable collapsible dependency tree
- `Graph` view for neighborhood or full-graph relationship inspection
- `Path from root` in the sidebar to explain why a package exists
- Search, keyboard pan/zoom, and box-zoom controls for graph inspection

---

## 🧪 Example Output

```text
Depsly Recommendations
Project: frontend
Packages analyzed: 204

1. eslint@9.39.4
   Action: REVIEW
   Actionability: MEDIUM
   Reason confidence: HIGH
   Impact: 35%
   Classification: Direct (root dev dependency)

   Why:
     - Direct dependency from root devDependencies
     - Structural impact: 35% (71 packages). Verify whether this dependency is still required
```

---

## 🧭 How to Read the Output

### Action
What Depsly suggests:

- REVIEW → investigate before changing  
- REMOVE → strong candidate to remove  
- TRACE_UPSTREAM → change parent dependency instead  
- DEFER → low priority  

---

### Actionability
How easy it is to change:

- HIGH → easy to modify  
- MEDIUM → moderate effort  
- LOW → difficult or risky  

---

### Impact
Percentage of your dependency graph affected.

---

### Reason confidence
How strong the structural signal is:

- HIGH → direct + clear signals  
- MEDIUM → inferred from structure  
- LOW → limited information  

---

## 🔁 Typical Workflow

```text
analyze → recommend → trace → simulate-remove
                 ↓
              save-scan → list-scans → compare-scans
                 ↓
              graph-html
```

---

## ⚠️ Important

Structural analysis only.  
Does not guarantee install, build, or runtime correctness.

---

## 🔐 Why Local-First Matters

- No source code upload  
- No account required  
- No rate limits  
- Fully deterministic  

---

## 🎯 Philosophy

Depsly is not a scanner.

It is a:

**Dependency decision support system**

---

## 📚 Docs

Run the CLI help to explore all commands and options:

```bash
depsly --help
```

For command-specific help:

```bash
depsly analyze --help
depsly recommend --help
depsly trace --help
depsly simulate-remove --help
depsly save-scan --help
depsly list-scans --help
depsly compare-scans --help
depsly graph-html --help
```

Example:

```bash
depsly recommend package-lock.json
```

---

## 🚧 Status

Early release (v0.1.11)

Core features are stable:
- analyze
- analyze --json
- recommend
- recommend --json
- trace
- trace --json
- simulate-remove
- simulate-remove --json
- save-scan
- list-scans
- compare-scans
- graph-html
  Explorer-first HTML report with collapsible tree, path view, and neighborhood graph
- telemetry
  Opt-in anonymous command-level usage telemetry with local queueing, batch flush, and reference ingest/reporting tooling
- scripts/scan_repos.py batch workflow

---

## 💬 Feedback

If you try Depsly on your project, I’d love to hear:
- what felt useful
- what felt off
- what you expected but didn’t see

Email: info+depsly@convologix.com
or open an issue on GitHub: https://github.com/sshiraz/depsly

Even a quick note or screenshot is incredibly helpful.

I read every message.

---

## 🏁 Summary

Depsly helps you move from:

“I have 200 dependencies…”

to:

“Here’s exactly what I should look at first.”
