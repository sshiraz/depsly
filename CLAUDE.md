# Depsly - AI Collaboration Rules (Elite)

This file defines how AI assistants (Claude Code, ChatGPT, etc.) must operate in this repository.

The goal is not just to generate code — it is to build a **high-performance, scalable dependency analysis system** with minimal waste, duplication, and rework.

---

# Primary Objective

Build Depsly as a:

- deterministic
- scalable
- graph-first
- analysis-driven

system for dependency risk intelligence.

NOT:
- a thin wrapper over LLMs
- a collection of scripts
- a loosely structured prototype

---

# Core Anti-Patterns (DO NOT DO)

## 1. No Duplicate Logic
- Never reimplement existing functionality in a new file
- Always search the codebase first
- Extend existing modules instead

## 2. No Premature Abstraction
- Do NOT introduce layers "just in case"
- Do NOT create interfaces without multiple real implementations
- Do NOT split files too early

## 3. No Fake Completeness
- Do NOT scaffold large systems with placeholder logic
- Do NOT create "empty architecture"
- Every function should do something real

## 4. No LLM Overuse
- Do NOT use LLM calls for:
  - scoring logic
  - deterministic analysis
  - graph processing
- LLM = optional explanation layer ONLY

## 5. No Unbounded Graph Traversal
- Never write naive recursion without:
  - depth awareness
  - cycle protection
  - memoization

---

# System Thinking (MANDATORY)

Depsly is fundamentally a:

> graph processing + analysis system

Every implementation must respect:

- nodes = packages
- edges = dependencies
- graph traversal cost grows rapidly
- same nodes appear repeatedly across graphs

---

# Architectural Principles

## 1. Separation of Concerns

Strict separation between:

- ingestion (input parsing)
- graph building (structure)
- analysis (risk logic)
- reporting (output)

DO NOT mix these.

---

## 2. Deterministic Core

Core logic must be:

- reproducible
- testable
- explainable
- not dependent on external randomness

---

## 3. Reusability of Graph Work

Graph traversal should:
- be written once
- reused everywhere
- avoid recomputation

---

## 4. Incremental Complexity

Always implement in this order:

1. simplest working version
2. validate correctness
3. optimize bottlenecks
4. generalize only if needed

---

# Development Workflow

## Before Writing Code

You MUST:

1. Read:
   - ARCHITECTURE.md
   - ROADMAP.md
   - MASTER_FEATURE_LIST.md

2. Check:
   - existing files
   - existing logic
   - prior documented decisions

3. Answer:
   - Where does this belong?
   - Does something similar already exist?
   - Can I extend instead of creating?

---

## For Any Non-Trivial Task

You MUST:

1. Propose a plan:
   - files to modify
   - new files (if any)
   - why

2. Wait for confirmation (if ambiguous)

3. Implement incrementally

---

## After Implementation

You MUST:

- explain what changed
- explain why it was done this way
- list follow-ups or risks
- update docs if needed:
  - DEV_LOG.md
  - update the relevant docs if a public-facing decision changes documentation
  - MASTER_FEATURE_LIST.md

---

# Performance Rules (CRITICAL)

## Graph Explosion Awareness

A single dependency can expand into hundreds.

You MUST:
- avoid repeated traversal
- reuse computed results
- cache where appropriate

---

## Memoization First

Before optimizing with complexity:
- cache results
- reuse node computations

---

## Avoid N^2 Patterns

Watch for:
- nested traversal loops
- repeated full graph scans
- redundant API calls

---

## Batching Over Repetition

Prefer:
- grouped operations
over:
- per-node expensive operations

---

# Testing Mindset

- Core logic must be testable without UI
- Graph logic must handle:
  - deep trees
  - repeated nodes
  - cycles (if applicable)
- Avoid hidden side effects

---

# Documentation Rules

## Always Update When:

- architecture changes → update ARCHITECTURE.md
- feature added → update MASTER_FEATURE_LIST.md
- meaningful work done → update DEV_LOG.md
- important decision made → update the relevant public docs if needed

---

# When You Are Unsure

You MUST:

- ask a clarifying question if blocked
- OR make the smallest reasonable assumption
- clearly state assumptions

DO NOT:
- hallucinate architecture
- invent missing systems
- create unnecessary files

---

# Strategic Direction Reminder

Depsly's edge is:

- dependency graph intelligence
- historical safety drift
- post-adoption monitoring

NOT:
- generic scanning
- surface-level vulnerability counts

---

# Definition of Good Output

A correct implementation:

- fits existing architecture
- avoids duplication
- is simple but extensible
- is performant for large graphs
- is explainable
- moves the product forward

---

# Definition of Bad Output

- duplicated modules
- over-engineered abstractions
- LLM-dependent logic
- unclear ownership of code
- premature scaling complexity
- placeholder-heavy code

---

# Final Rule

When in doubt:

> Prefer simple, correct, and extendable
> over clever, abstract, or speculative
