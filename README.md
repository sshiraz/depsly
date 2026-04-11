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

So you can decide **where to spend your time**.

---

## ✨ What Depsly Does

- Builds a full dependency graph from `package-lock.json`
- Analyzes structural risk (depth, fanout, transitive exposure)
- Ranks dependencies by **impact × actionability**
- Explains why transitive dependencies exist
- Simulates structural impact of removing packages
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

---

### Get prioritized recommendations

```bash
depsly recommend package-lock.json
```

---

### Trace why a package exists

```bash
depsly trace package-lock.json @babel/core@7.29.0
```

---

### Preview structural impact of removal

```bash
depsly simulate-remove package-lock.json eslint@9.39.4
```

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
   Classification: Direct (dev dependency)

   Why:
     - Direct dev dependency (user-controlled)
     - Structural impact: 35% (71 packages)
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
```

Example:

```bash
depsly recommend package-lock.json
```

---

## 🚧 Status

Early release (v0.1.4)

Core features are stable:
- analyze
- recommend
- recommend --json
- trace
- simulate-remove

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
