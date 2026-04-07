# Depsly Product Requirements Document (PRD)

## 1. Overview

### Product Name
Depsly

### Tagline
From dependency hell to dependency zen.

### Product Category
Developer tooling / Dependency analysis / Decision intelligence

---

## 2. Problem Statement

Modern software projects rely heavily on open-source dependencies. These dependencies introduce:

- Deep and opaque dependency trees
- Transitive risk amplification
- Hidden coupling and fragility
- High-cost refactoring decisions

Existing tools focus on:
- Vulnerability detection
- Compliance reporting

But they do NOT answer:
- What should I fix first?
- What happens if I remove or replace a dependency?
- Is this change feasible?

---

## 3. Solution

Depsly is a deterministic dependency decision engine that:

1. Builds a full dependency graph from lockfiles
2. Computes structural risk metrics
3. Simulates dependency changes (remove, replace)
4. Recommends high-impact, feasible actions

---

## 4. Goals

### Primary Goals
- Provide actionable recommendations
- Enable safe what-if simulations
- Maintain deterministic outputs
- Support local-first workflows

### Secondary Goals
- Enable iterative refactoring workflows
- Provide CI integration foundation
- Support future UI exploration

---

## 5. Non-Goals (MVP)

- Runtime correctness guarantees
- Full static code analysis
- LLM-dependent scoring
- Enterprise compliance reporting

---

## 6. Target Users

### Primary
- Software engineers
- Tech leads
- Dev teams managing large JS/TS projects

### Secondary
- Security-focused teams
- DevOps engineers

---

## 7. Core Value Proposition

Depsly shows you what to change, what happens if you change it, and whether it is realistic — before touching your code.

---

## 8. Functional Requirements

### 8.1 Input
- package-lock.json (initial)
- Future: yarn.lock, pnpm-lock.yaml

### 8.2 Graph Engine
- Directed graph (nodes = packages, edges = dependencies)
- Cycle detection
- Depth calculation
- Transitive resolution

### 8.3 Analysis Engine
Metrics:
- Nodes, edges, depth
- Direct/transitive counts
- Leaf count
- Fanout

Risk Score Components:
- Depth risk
- Size risk
- Transitive ratio
- Centralization

Must be deterministic.

---

### 8.4 Simulation Engine

#### simulate-remove
Command:
depsly simulate-remove <lockfile> <package>

Outputs:
- Nodes removed
- Percent reduction
- Impacted packages

Constraint:
Structural only (no runtime guarantees)

---

### 8.5 Decision Engine (Critical)

#### recommend
Goal: rank packages by impact and feasibility

Impact:
impact = removed_nodes / total_nodes

Feasibility factors:
- Direct dependency (+)
- Dev dependency (+)
- High fanout (-)
- Deep node (-)

Final score:
score = impact * feasibility

---

### 8.6 Execution Awareness

#### classification
- Direct
- Transitive
- Dev
- Root

#### trace
Command:
depsly trace <package>

Output:
dependency chain showing origin

---

## 9. Non-Functional Requirements

### Performance
- Handle large graphs (1000+ nodes)

### Determinism
- Same input → same output

### Security
- No source code required
- Local-first execution

---

## 10. UX Requirements

### CLI
Commands:
- analyze
- simulate-remove
- recommend
- trace

Readable structured output required.

---

## 11. Trust

Users should not need to upload source code.

Messaging:
- No source code required
- Runs locally
- Deterministic

---

## 12. Monetization

Free:
- analyze
- simulate-remove

Paid:
- recommendations
- CI integration
- advanced simulations

---

## 13. Risks

- False confidence → add disclaimers
- Non-actionable output → add feasibility + trace
- Competition → emphasize determinism

---

## 14. Roadmap

Phase 1:
- recommend
- feasibility scoring

Phase 2:
- classification
- trace

Phase 3:
- simulate-replace

Phase 4:
- UI

---

## 15. Success Metrics

- Time to insight < 30 seconds
- Repeat usage
- Actionable recommendations

---

## Final Goal

User runs:
depsly recommend package-lock.json

And knows exactly what to change and why.
