# program.md — Autonomous Research Goals for Agent Swarm Studio

> Inspired by karpathy/autoresearch: this file defines the research direction
> for autonomous daily improvement of the agent-swarm-studio codebase.
> Edit this file to steer what the daily review agent focuses on.

---

## Current Research Goals (in priority order)

### 1. Agent Intelligence Loop
Make each agent smarter per task cycle. The ideal end state is agents that:
- Plan before acting (explicit reasoning step)
- Use tools in sequence (search → fetch → synthesize → verify)
- Self-critique their output before returning it
- Track experiment results and improve over time (like autoresearch train.py iterations)

### 2. Swarm Coordination
Improve how agents hand off work to each other:
- Orchestrator should decompose complex tasks and assign sub-tasks in parallel
- Agents should be able to request help from peer agents mid-task
- Results should be aggregated and synthesized, not just concatenated

### 3. Memory & Continuity
Agents currently lose context between tasks. Target improvements:
- Persistent per-agent memory that survives restarts
- Cross-agent shared knowledge base (what one agent learns, others can query)
- Task history used to improve future task planning

### 4. Observability & Debugging
The UI shows logs but not agent reasoning. Target:
- Expose intermediate reasoning steps in the log stream
- Show which tools were called and what they returned
- Enable replaying a task from any point

### 5. Hot-Swap & Registry
The registry/hot-swap system exists — make it smarter:
- Agents should be able to propose their own replacement when stuck
- Registry should score agents by task success rate and auto-promote better versions

---

## What to Look For in Each Review

For each daily review, examine the main branch and identify:

1. **One concrete bug or limitation** — something that would break in real use
2. **One performance or quality improvement** — something that would make outputs better
3. **One developer experience improvement** — something that makes the codebase easier to extend
4. **Alignment check** — are we getting closer to the autoresearch pattern? What's the next step?

---

## The Autoresearch Pattern (target end state)

From karpathy/autoresearch: the agent should be able to run unsupervised overnight and wake you up with a log of experiments. For agent-swarm-studio, this means:

- Agent receives a goal
- Agent plans a sequence of sub-experiments
- Each experiment runs, is evaluated, kept or discarded
- Results accumulate in memory
- You wake up to a report of what was tried and what improved

We are not there yet. Each daily review should move us one step closer.

---

## Fixed Reference Points (do not change these)
- Repo: https://github.com/travis-burmaster/agent-swarm-studio
- Reference pattern: https://github.com/karpathy/autoresearch
- Metric to optimize: quality and completeness of agent task output (subjective, but reviewable)
