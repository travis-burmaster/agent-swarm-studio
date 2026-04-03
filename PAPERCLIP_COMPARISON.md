# Agent Swarm Studio vs. Paperclip — Architecture Comparison

> **Context:** This document was written as part of `feat/paperclip-patterns`,
> a branch that adopts two structural conventions from
> [paperclipai/paperclip](https://github.com/paperclipai/paperclip) into
> Agent Swarm Studio. It explains what Paperclip is, how the two projects
> differ, what we borrowed, and what we deliberately did not adopt.

---

## What Is Paperclip?

[Paperclip](https://github.com/paperclipai/paperclip) (45K+ GitHub stars,
MIT, TypeScript/Node.js) is an open-source **company operating system** for
AI agents. Its tagline is "orchestration for zero-human companies."

Where most agent frameworks focus on individual agent capability, Paperclip
focuses on **organizational structure** — giving agents an org chart, a budget,
goals, approval gates, and governance. You define a company; Paperclip runs it.

**Core Paperclip concepts:**
- **Companies** — top-level organizational unit; all agents and tasks are scoped to one
- **Heartbeats** — agents wake on a cron schedule, assess state, take action autonomously
- **Atomic task checkout** — `SETNX`-style lock prevents two agents grabbing the same task
- **Approval gates** — governed actions require human sign-off before execution
- **Adapter layer** — pluggable runtimes: Claude Code, Codex, Cursor, OpenClaw, etc.
- **Budget hard-stops** — per-agent spend caps with auto-pause
- **`.agents/skills/` convention** — each skill is a folder with `SKILL.md` + `references/`

**Tech stack:** Node.js 20+, pnpm monorepo, React + Vite UI, Drizzle ORM,
embedded PGlite (dev) / PostgreSQL (prod), Express REST API.

---

## Side-by-Side Comparison

| Dimension | Agent Swarm Studio | Paperclip |
|-----------|-------------------|-----------|
| **Purpose** | Domain-specialist intelligence for company analysis | Horizontal operating system for any AI-agent company |
| **Scope** | Vertical product (4 specialist agents, one workflow) | Horizontal platform (any agents, any workflows) |
| **Language** | Python | TypeScript |
| **LLM access** | Direct Anthropic API or OAuth proxy | Pluggable adapter layer (Claude, Codex, Cursor, etc.) |
| **Agent identity** | SOUL.md + RULES.md + AGENTS.md + INSTRUCTIONS.md | Skill injection via `.agents/skills/` |
| **Task queue** | Redis `brpop` | Redis `SETNX` atomic checkout |
| **Persistence** | PostgreSQL (raw asyncpg) | PostgreSQL via Drizzle ORM with migrations |
| **Scheduling** | `scheduler.yml` (custom) | Heartbeat cron system |
| **Governance** | Rules-based (RULES.md) | Approval gates + budget hard-stops |
| **Skills** | `skills/{domain}/*.md` | `.agents/skills/{name}/SKILL.md` + `references/` |
| **Registry** | gitagent-compatible `agent.yaml` | None (self-hosted only) |
| **Shared URL context** | `TARGET_COMPANY_URL` env var | Not applicable |
| **Web search** | agent-search-tool (15+ platforms) | Not built-in |
| **CI/CD** | None | Full GitHub Actions (release, e2e, PR checks) |
| **Stars** | — | 45,597 |

---

## What Agent Swarm Studio Does That Paperclip Does Not

### 1. Shared Agent Identity Layer
Every agent in this swarm loads four shared files at startup:

```
SOUL.md        — shared character, values, mission
RULES.md       — 10 non-negotiable operating rules
AGENTS.md      — roster, collaboration flow, handoff protocol
INSTRUCTIONS.md — step-by-step execution handbook
```

Paperclip has no equivalent. Its agents are generic workers that receive
tasks; ours are specialists with a shared conscience and operating contract.

### 2. Domain-Specialist Prompts
Each agent has a deep domain prompt (500–800 lines) encoding:
- Professional identity and expertise
- Domain-specific analysis framework (8+ dimensions)
- Tool usage examples with real code
- Structured output templates with example tables
- What the agent explicitly is not (scope boundaries)

Paperclip agents are runtime-agnostic; specialization is left to the user.

### 3. `TARGET_COMPANY_URL` — Shared Research Context
A single environment variable synchronizes all four agents onto the same
research target. The `agent_runner.py` also caches each agent's output in
Redis (`agent:output:{agent_id}:{url_slug}`) so downstream agents can build
on upstream findings before starting their own analysis.

Paperclip has no concept of a shared data context across agents.

### 4. agent-search-tool Integration
Every agent container has `agent-search-tool` (Travis's own library) installed,
giving live access to web, GitHub, Reddit, Twitter, YouTube, LinkedIn, and
Exa Search. This means agents work from real-time public data, not just their
training knowledge.

### 5. gitagent Registry Compatibility
The `agent.yaml` at the root follows the
[gitagent registry](https://registry.gitagent.sh) schema, making this swarm
publishable to the registry with `gitagent publish`.

---

## What We Borrowed From Paperclip in This PR

### 1. `.agents/skills/` Folder Convention

**Before (our original structure):**
```
skills/
  lawyer/
    contract-review.md
    compliance-check.md
    risk-analysis.md
  data-researcher/
    market-analysis.md
    ...
```

**After (Paperclip convention):**
```
.agents/
  skills/
    lawyer/
      SKILL.md              ← primary skill (contract review)
      references/
        compliance-check.md ← supporting reference
        risk-analysis.md    ← supporting reference
    data-researcher/
      SKILL.md
      references/
        competitive-intel.md
        financial-research.md
    marketing/
      SKILL.md
      references/
        content-strategy.md
        brand-positioning.md
    sales/
      SKILL.md
      references/
        icp-profiling.md
        revenue-modeling.md
```

**Why this matters:**
- `.agents/` is a hidden dot-directory (like `.github/`, `.claude/`), signaling
  "agent infrastructure, not product code" — cleaner repo separation
- `SKILL.md` as the primary entry point with `references/` for supporting docs
  mirrors how Paperclip structures skills — consistent with an emerging convention
- Makes the repo compatible with tools that scan for `.agents/skills/*/SKILL.md`

### 2. Atomic Task Checkout (Redis `SETNX` Lock)

**Before:**
```python
result = await r.brpop(TASK_QUEUE_KEY, timeout=5)
# ← race condition: if same task_id lands in queue twice, two agents
#   could both pop it and process it simultaneously
```

**After:**
```python
result = await r.brpop(TASK_QUEUE_KEY, timeout=5)
# Acquire exclusive lock before processing
lock_key = f"task:lock:{task_id}"
acquired = await r.set(lock_key, AGENT_ID, nx=True, ex=600)
if not acquired:
    logger.warning("Task %s already locked by another worker — skipping", task_id)
    continue
# ← guaranteed single-agent execution per task_id
```

**Why this matters:**
- Prevents duplicate processing when tasks are retried or re-queued on error
- Safe for future horizontal scaling (multiple containers per agent type)
- Matches Paperclip's "single-assignee task model" invariant, which they
  consider a core control-plane guarantee

---

## What We Deliberately Did Not Adopt

### Drizzle ORM / TypeScript Migration
Paperclip uses Drizzle for typed, versioned schema management. Our stack is
Python + asyncpg with raw SQL. A full migration to TypeScript would be a
rewrite, not a pattern adoption. The raw SQL approach is simpler for a
focused 4-agent product.

### Heartbeat System
Paperclip's heartbeat model (agents wake on cron, assess state, act) is more
autonomous than our queue-based model. Our `scheduler.yml` achieves similar
scheduling outcomes with less complexity. Worth revisiting if we need agents
to self-initiate work without a task being explicitly queued.

### Approval Gates
Paperclip's governed action system requires human approval for certain agent
actions. Our RULES.md-based governance is softer (agents self-constrain via
rules rather than hard gates). For a business intelligence swarm producing
reports, hard gates add friction without much safety benefit.

### Adapter Layer
Paperclip's pluggable adapter architecture (Claude, Codex, Cursor, etc.) would
let us swap LLM backends. Our agents are Claude-specific by design — the
specialist prompts are tuned for Claude's reasoning style. Adding an adapter
layer is premature until there's a reason to switch models.

### Budget Hard-Stops
Cost controls are on the roadmap but not implemented here. The `agent.yaml`
has stubs for per-agent budget configuration.

---

## Convergences — Patterns We Built Independently That Match

It's notable that several patterns we arrived at independently mirror Paperclip's
architecture:

| Our Pattern | Paperclip Equivalent |
|-------------|---------------------|
| `AGENTS.md` as shared contributor + agent contract | `AGENTS.md` at repo root with identical purpose |
| `skills/{domain}/` for agent sub-capabilities | `.agents/skills/{name}/SKILL.md` |
| Redis pub/sub for real-time event streaming | Redis pub/sub events |
| PostgreSQL for long-term agent memory | PostgreSQL for task/activity persistence |
| Shared workspace volume between agents | Shared file context between agents |

This convergence suggests these are load-bearing patterns in multi-agent system
design — not coincidences.

---

## Relationship Between the Two Projects

These projects are complementary, not competitive.

Paperclip is a **platform** — it could run this swarm as one of its "companies,"
with the four agents as department heads. Agent Swarm Studio is a **product** —
a fully-configured, opinionated intelligence operation that happens to be built
on the same foundational patterns.

A future integration path: publish this swarm to the gitagent registry, then
let Paperclip operators instantiate it as a pre-built company template.

---

*Comparison accurate as of April 2026.*
*Paperclip repo: [github.com/paperclipai/paperclip](https://github.com/paperclipai/paperclip)*
*Agent Swarm Studio: [github.com/travis-burmaster/agent-swarm-studio](https://github.com/travis-burmaster/agent-swarm-studio)*
