# INSTRUCTIONS.md — Task Execution Handbook

> Step-by-step operational guide for every agent.
> Read this once per session. Follow it on every task.

---

## 1. Startup Sequence

When your container starts, execute this sequence before accepting any tasks:

```python
# Step 1: Load your identity files
# (agent_runner.py handles this automatically)
# SOUL.md → your character
# RULES.md → your operating constraints
# AGENTS.md → your team and protocols
# INSTRUCTIONS.md → this file

# Step 2: Initialize agent-search-tool
from agent_search import AgentReach
import os
reach = AgentReach()
health = reach.doctor()
if not health.all_ok:
    logger.warning(f"Search channels degraded: {health.failed_channels}")

# Step 3: Read the shared URL context
company_url = os.getenv("TARGET_COMPANY_URL", "")
if company_url:
    logger.info(f"Target company URL set: {company_url}")

# Step 4: Announce ready status to Redis
await update_status(redis, "idle")
```

---

## 2. Task Intake Procedure

When a task arrives in your Redis queue:

### 2a. Parse the task
```python
task = json.loads(raw_message)
task_id = task["task_id"]
description = task["description"]
company_url = task.get("context", {}).get("company_url") or os.getenv("TARGET_COMPANY_URL")
prior_findings = task.get("context", {}).get("prior_findings", "")
```

### 2b. Acknowledge the task (Rule 7)
Output immediately:
```
[TASK RECEIVED] Analyzing [company name] for [your domain] intelligence.
```

### 2c. Load prior findings
If another agent has already analyzed this company, load their findings
from Redis or PostgreSQL before starting. Do not duplicate work they already did.

```python
# Check for existing research context
context_key = f"company:context:{company_url_slug}"
existing_context = await redis.get(context_key)
```

---

## 3. Research Execution

### 3a. Fetch the company URL first
```python
# Always start here
company_data = reach.fetch(company_url)

# Then go deeper based on your role
# Examples:
web_results = reach.search(f"site:{domain} legal privacy terms")  # lawyer
github_results = reach.search(f"org:{company_name} site:github.com")  # researcher
reddit_results = reach.search(f"{company_name} reddit review")  # researcher/marketing
twitter_results = reach.search(f"{company_name} twitter")  # marketing
```

### 3b. Research depth by agent role

**lawyer:** Read ToS, Privacy Policy, About page, any /legal subdirectory.
Search for "company name lawsuit", "company name SEC filing", "company name
regulatory". Check job postings for compliance/legal role signals.

**data-researcher:** Read About, Blog, Pricing, Customers/Case Studies pages.
Search GitHub for the org. Search Crunchbase, LinkedIn, press releases.
Look at job postings for team growth signals. Check Reddit and HN for
community sentiment.

**marketing:** Read the homepage, About, Blog, and all landing pages.
Check meta tags and structured data in the HTML. Search for the company's
keywords in Google. Find top 3 competitors via search and compare.
Check Twitter/LinkedIn presence.

**sales:** Read Pricing page in detail. Read all customer case studies and
testimonials. Look at the integrations/partnerships page. Check job postings
for AE, SDR, CSM roles as growth signals. Look for press releases about
enterprise deals or ARR milestones.

---

## 4. Output Construction

Follow the standard output format from RULES.md Rule 5. Do not skip sections.

### 4a. Executive Summary
Write this last, after you have all findings. Keep it to 3 sentences max.
Lead with the single most important thing you found.

### 4b. Key Findings
Number every finding. Attach a source to every finding. Group by sub-topic.
Minimum 5 findings; aim for 10–15 substantive findings per analysis.

### 4c. Risk / Opportunity Matrix
Every agent produces this table, framed for their domain:
- lawyer → legal risks + regulatory opportunities
- data-researcher → market risks + growth opportunities
- marketing → SEO/brand gaps + positioning opportunities
- sales → revenue risks + pipeline opportunities

### 4d. Recommendations
3–7 specific, actionable recommendations with priority (P1/P2/P3).
P1 = act within 30 days. P2 = act within 90 days. P3 = strategic, 6+ months.

### 4e. Handoff Notes
Only include if you found something clearly in another agent's domain.
Format: `→ [agent-id]: [what you found and why it matters to them]`

---

## 5. Memory Storage

After every task, write a memory record:

```python
await store_memory(db_pool, "assistant",
    f"""
    TASK COMPLETE — {agent_id} analysis of {company_url}
    Date: {datetime.utcnow().isoformat()}
    Company: {company_name}
    Top 3 findings:
    1. {finding_1}
    2. {finding_2}
    3. {finding_3}
    Handoffs: {handoff_summary}
    Open questions: {open_questions}
    """
)
```

Also cache the full output for other agents:
```python
await redis.set(
    f"agent:output:{agent_id}:{company_url_slug}",
    json.dumps({"output": full_output, "timestamp": now}),
    ex=86400  # 24-hour TTL
)
```

---

## 6. Error Handling

| Error Type | Response |
|-----------|----------|
| URL unreachable | Report it, analyze what can be found elsewhere, flag as `[UNVERIFIED]` |
| Search channel down | Continue with working channels, note degraded search in output |
| Empty search results | Report "no results found for [query]" — do not fabricate |
| Task parse error | Log error, publish `task_error` event, return to idle |
| LLM rate limit | Retry with exponential backoff (3x), then fail gracefully |

---

## 7. Synthesis Mode

When the orchestrator requests a synthesis (all 4 agents have completed):

The backend combines all four outputs and produces:

```
## Business Intelligence Report — [Company Name]

### Swarm Consensus
[What all 4 agents agree on]

### Legal Intelligence (lawyer)
[Lawyer's executive summary + top 3 findings]

### Market Intelligence (data-researcher)
[Researcher's executive summary + top 3 findings]

### Marketing Intelligence (marketing)
[Marketing's executive summary + top 3 findings]

### Revenue Intelligence (sales)
[Sales' executive summary + top 3 findings]

### Cross-Agent Risk Flags
[Items flagged by 2+ agents]

### Unified Recommendations
[Merged P1/P2/P3 action list across all domains]
```

---

## 8. Versioning

These instructions track with `agent.yaml` version. If you load a task
where the `agent.yaml` version does not match your loaded version, log a
warning but proceed — do not block on version mismatch.

*Current version: 2.0.0*
