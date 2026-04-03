# Agent Swarm Studio — Business Intelligence Swarm

A collaborative swarm of four AI specialists that analyze any company URL —
or answer any question — from every angle simultaneously. Point the swarm at
a URL for a quick scan, or ask a free-form question and get specialist
perspectives from all agents with an orchestrator-synthesized summary.

---

## The Agents

| Agent | Role | What It Does |
|-------|------|-------------|
| **Lawyer** | Corporate Intelligence | Legal scan, ToS/privacy analysis, compliance gaps, litigation signals |
| **Data Researcher** | Market Intelligence | Company profile, competitive landscape, tech stack, funding signals |
| **Marketing** | SEO & Brand | On-page SEO audit, content strategy, brand positioning, competitor keyword gaps |
| **Sales** | Revenue Intelligence | Pricing model, ICP profiling, GTM motion, partnership opportunities |

All four agents share a common identity (`SOUL.md`), operating rules (`RULES.md`),
team protocol (`AGENTS.md`), and execution instructions (`INSTRUCTIONS.md`).

---

## Quick Start

### 1. Clone and configure
```bash
git clone https://github.com/travis-burmaster/agent-swarm-studio.git
cd agent-swarm-studio
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY and set TARGET_COMPANY_URL
```

### 2. Start the swarm
```bash
docker compose up --build
```

### 3. Use the UI

Open **http://localhost:3000**. There are two ways to engage the swarm:

**Ask the Swarm** — Type any question in the top bar and click **Ask All Agents**.
Each agent answers from its specialist perspective, and the orchestrator
synthesizes a unified summary when all agents complete. If a URL is set in the
Analyze bar, it's included as context.

**Analyze a URL** — Enter a company URL and click **Analyze** for a quick
full-spectrum scan (legal, market, SEO, revenue) with orchestrator synthesis.

When the orchestrator summary is ready, a **View Summary** button appears in the
header.

You can also **Chat with any agent** directly via the Chat buttons on each agent
card, or **Chat with the Orchestrator** from the task panel to ask follow-up
questions across all findings.

### 4. Use the API

```bash
# Ask a question across all agents
curl -X POST http://localhost:8000/workflow/question \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the risks of entering the fintech market?", "company_url": "https://stripe.com"}'

# Run a URL analysis
curl -X POST http://localhost:8000/workflow/analyze \
  -H "Content-Type: application/json" \
  -d '{"company_url": "https://stripe.com"}'

# Create a single task for one agent
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Analyze pricing strategy", "assign_to": "sales"}'
```

### 5. Watch in real-time
Subscribe to the WebSocket event stream:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## Configure agent-search-tool

Each agent container has `agent-search-tool` installed. Configure it once:

```bash
# Configure web + GitHub search (minimum recommended)
docker exec agent-data-researcher agent-search configure

# Check health across all agents
docker exec agent-lawyer agent-search doctor
docker exec agent-data-researcher agent-search doctor
docker exec agent-marketing agent-search doctor
docker exec agent-sales agent-search doctor
```

For richer results, configure:
- `EXA_API_KEY` — semantic web search ([exa.ai](https://exa.ai))
- `GITHUB_TOKEN` — deeper GitHub org/repo research

---

## Architecture

```
                    ┌─────────────────────┐
                    │   React UI (:3000)   │
                    └────────┬────────────┘
                             │ HTTP + WebSocket
                    ┌────────▼────────────┐
                    │  FastAPI Backend     │
                    │     (:8000)          │
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌─────▼─────┐  ┌───▼────┐
         │  Redis   │   │ PostgreSQL │  │  YAML  │
         │ (queue + │   │ (memory + │  │ config │
         │ pub/sub) │   │  tasks)   │  └────────┘
         └────┬─────┘   └───────────┘
              │
    ┌─────────┼──────────┬──────────────┐
    │         │          │              │
┌───▼──┐ ┌───▼──────┐ ┌─▼────────┐ ┌──▼───┐
│Lawyer│ │Researcher│ │Marketing │ │Sales │
│agent │ │  agent   │ │  agent   │ │agent │
└──────┘ └──────────┘ └──────────┘ └──────┘
    │         │          │              │
    └─────────┴──────────┴──────────────┘
              │
     agent-search-tool
    (web, github, reddit,
     twitter, youtube, exa)
```

---

## File Structure

```
agent-swarm-studio/
├── agent.yaml              # gitagent-compatible swarm config
├── SOUL.md                 # Shared identity and values
├── RULES.md                # Operating rules for all agents
├── AGENTS.md               # Agent roster and collaboration protocol
├── INSTRUCTIONS.md         # Task execution handbook
├── scheduler.yml           # Cron and event-based scheduling
├── docker-compose.yml      # Full stack definition
├── .env.example            # Environment variable template
│
├── agents/
│   ├── base/
│   │   ├── agent_runner.py # Core agent loop (loads SOUL/RULES/AGENTS/INSTRUCTIONS)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── lawyer/
│   │   └── prompt.md       # Lawyer specialist prompt
│   ├── data-researcher/
│   │   └── prompt.md       # Researcher specialist prompt
│   ├── marketing/
│   │   └── prompt.md       # Marketing/SEO specialist prompt
│   └── sales/
│       └── prompt.md       # Revenue/Sales specialist prompt
│
├── skills/
│   ├── lawyer/
│   │   ├── contract-review.md
│   │   ├── compliance-check.md
│   │   └── risk-analysis.md
│   ├── data-researcher/
│   │   ├── market-analysis.md
│   │   ├── competitive-intel.md
│   │   └── financial-research.md
│   ├── marketing/
│   │   ├── seo-audit.md
│   │   ├── content-strategy.md
│   │   └── brand-positioning.md
│   └── sales/
│       ├── pipeline-analysis.md
│       ├── icp-profiling.md
│       └── revenue-modeling.md
│
├── backend/                # FastAPI backend
└── ui/                     # React/Vite frontend
```

---

## gitagent Compatibility

This repo follows the [gitagent](https://registry.gitagent.sh) agent definition
format. The `agent.yaml` file at the root defines all agents, their models,
skills, and workflows in a registry-compatible schema.

To publish to the gitagent registry:
```bash
gitagent publish --config agent.yaml
```

---

## Extending the Swarm

### Add a new agent
1. Create `agents/{name}/prompt.md` with the specialist prompt
2. Create `skills/{name}/` directory with skill files
3. Add the agent definition to `agent.yaml`
4. Add the service to `docker-compose.yml` following the existing pattern

### Add a new workflow
Define it in `scheduler.yml` under `workflows:` and reference it via:
```bash
curl -X POST http://localhost:8000/tasks \
  -d '{"description": "...", "workflow": "your_workflow_name"}'
```

---

## Credits

- Built on [Agent Swarm Studio](https://github.com/travis-burmaster/agent-swarm-studio)
- Search powered by [agent-search-tool](https://github.com/travis-burmaster/agent-search-tool)
- Agent format inspired by [gitagent registry](https://registry.gitagent.sh)
- LLM: [Claude](https://anthropic.com) (claude-sonnet-4-6)
