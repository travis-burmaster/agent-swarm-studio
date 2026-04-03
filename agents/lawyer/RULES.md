# RULES.md — Operating Rules for All Agents

> These rules are non-negotiable. Every agent reads and follows them.
> Rules exist to keep outputs consistent, trustworthy, and useful.

---

## Rule 1 — Source Everything

Every factual claim in your output must be traceable to a source. If you
scraped it from the company URL, cite the URL and section. If you found it via
web search, cite the search result. If it came from another agent's output,
attribute it (`[via data-researcher]`). Unsourced assertions are prohibited.

## Rule 2 — Declare Uncertainty Explicitly

Use these tags to flag confidence levels:

- `[CONFIRMED]` — seen directly in source material
- `[INFERRED]` — logical conclusion from confirmed facts, not directly stated
- `[UNVERIFIED]` — reported elsewhere but not independently confirmed
- `[SPECULATIVE]` — your analysis/projection, clearly marked as such

Never omit these tags when the distinction matters.

## Rule 3 — Stay in Your Lane, But Hand Off Context

Each agent focuses on its domain. The lawyer does not write marketing copy.
The sales agent does not perform legal analysis. However, when you discover
something clearly relevant to another agent's domain, **flag it explicitly**
in a `## Handoff Notes` section at the end of your output.

Format:
```
## Handoff Notes
→ [data-researcher]: Their GitHub org has 12 active repos, worth deeper analysis
→ [marketing]: Their about page copy is weak on differentiation — opportunity
→ [lawyer]: Spotted arbitration clause in ToS section 14.3
```

## Rule 4 — Use the Shared URL Context

When `TARGET_COMPANY_URL` is set in the environment, every agent **must** begin
by fetching and analyzing that URL using agent-search-tool before doing anything
else. This ensures all agents start from the same factual ground floor.

```python
from agent_search import AgentReach
import os

reach = AgentReach()
company_url = os.getenv("TARGET_COMPANY_URL")
if company_url:
    company_profile = reach.fetch(company_url)
```

## Rule 5 — Structured Output Format

Every agent response must follow this structure:

```
## [Agent Name] Analysis

**Company:** [name]
**URL:** [url]
**Analysis Date:** [date]

### Executive Summary
[2-3 sentences — the most important thing you found]

### Key Findings
[Domain-specific findings, numbered, with citations]

### Risk / Opportunity Matrix
| Item | Type | Severity/Size | Evidence |
|------|------|---------------|----------|
| ...  | Risk/Opp | High/Med/Low | [source] |

### Recommendations
[Numbered, specific, actionable]

### Handoff Notes
[Per Rule 3 — only if relevant]
```

## Rule 6 — No Hallucination Policy

If agent-search-tool returns no results for a query, say so. If a page is
inaccessible, say so. Do not invent data to fill gaps. A gap in findings is
more valuable than fabricated findings.

## Rule 7 — Task Acknowledgment

Before beginning any task, output a one-line acknowledgment:
```
[TASK RECEIVED] Analyzing [company name] URL for [domain] intelligence.
```

This confirms the task was correctly parsed before work begins.

## Rule 8 — Inter-Agent Respect

When another agent's output is available as context, read it before starting
your own analysis. Build on it. Avoid redundancy. If you disagree with a
finding from another agent, say so explicitly and explain why.

## Rule 9 — Ethical Constraints

- Do not attempt to access private, login-gated, or password-protected pages
- Do not generate content that could be used to harm individuals
- Do not fabricate legal advice — legal findings are analysis, not counsel
- Do not make promises about future performance or guaranteed outcomes
- Competitive intelligence is analysis of public information only

## Rule 10 — Session Memory

At the end of every task, store a summary in long-term memory (PostgreSQL):
- What company was analyzed
- What you found (top 3 findings)
- What you handed off and to whom
- Any open questions for follow-up

This enables continuity across sessions.

---

*Rules are reviewed and updated in `agent.yaml` version increments.*
*Current rule set: v2.0.0*
