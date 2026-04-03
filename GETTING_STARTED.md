# Getting Started with Agent Swarm Studio

A Business Intelligence Swarm that deploys four specialist AI agents to analyze any company URL from multiple angles simultaneously — legal, market research, marketing/SEO, and revenue/sales.

---

## Prerequisites

- **Docker** & **Docker Compose** (v2+)
- An **Anthropic API key** (`sk-ant-...`) or an **OAuth token**
- _(Optional)_ [agent-search-tool](https://pypi.org/project/agent-search-tool/) API keys for web/GitHub/Reddit search channels

---

## Quick Start

```bash
# 1. Clone and enter the project
cd agent-swarm-studio

# 2. Create your .env from the example
cp .env.example .env

# 3. Edit .env — at minimum set one of:
#    ANTHROPIC_API_KEY=sk-ant-...
#    or
#    ANTHROPIC_OAUTH_KEY=...

# 4. Build and start the full stack
docker compose up --build
```

Once running:

| Service        | URL                              |
|----------------|----------------------------------|
| **UI**         | http://localhost:3000             |
| **API**        | http://localhost:8000             |
| **Health**     | http://localhost:8000/health      |
| **WebSocket**  | ws://localhost:8000/ws/events     |

---

## Environment Variables

```bash
# --- LLM Access (pick one) ---
ANTHROPIC_API_KEY=sk-ant-...           # Direct API key
ANTHROPIC_OAUTH_KEY=...                # OAuth token (routes through proxy)

# --- Database ---
POSTGRES_USER=agentuser
POSTGRES_PASSWORD=changeme_secure_password
POSTGRES_DB=agents

# --- Redis (defaults work with docker-compose) ---
REDIS_URL=redis://redis:6379

# --- Target (optional, can also be set per-task in the UI) ---
TARGET_COMPANY_URL=https://example.com

# --- Search channels (optional, enhances agent research) ---
# EXA_API_KEY=...
# GITHUB_TOKEN=...
```

---

## Architecture Overview

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React UI   │────>│   FastAPI    │────>│    Redis     │
│  :3000       │<────│   Backend    │<────│   :6379      │
│  (nginx)     │ WS  │   :8000      │     │  queues/pub  │
└──────────────┘     └──────┬───────┘     └──────┬───────┘
                            │                     │
                     ┌──────┴───────┐      ┌──────┴───────┐
                     │  PostgreSQL  │      │  Agent x4    │
                     │  :5432       │      │  (BRPOP)     │
                     │  tasks/memory│      │  lawyer      │
                     └──────────────┘      │  researcher  │
                                           │  marketing   │
                                           │  sales       │
                                           └──────────────┘
```

### Stack

| Component       | Tech                                      |
|-----------------|-------------------------------------------|
| Frontend        | React 18, TypeScript, Tailwind, Vite      |
| Backend         | FastAPI, Uvicorn, asyncpg, aioredis       |
| Agents          | Python 3.12, Anthropic SDK, agent-search  |
| Proxy           | curl-cffi (OAuth token proxy, optional)   |
| Database        | PostgreSQL 16                             |
| Queue / PubSub  | Redis 7                                   |

---

## The Four Agents

| Agent              | Focus                    | What It Produces                                           |
|--------------------|--------------------------|------------------------------------------------------------|
| **lawyer**         | Legal & Compliance       | ToS/privacy analysis, compliance gaps, litigation signals  |
| **data-researcher**| Market Intelligence      | Company profile, tech stack, funding, competitive landscape|
| **marketing**      | SEO & Brand              | On-page SEO audit, content strategy, keyword gaps          |
| **sales**          | Revenue & GTM            | Pricing model, ICP profiling, GTM motion, revenue estimate |

All agents share a common identity defined by four files at the project root:

- **SOUL.md** — Shared values and mission
- **RULES.md** — 10 operating rules (source everything, declare uncertainty, etc.)
- **AGENTS.md** — Collaboration protocol and handoff format
- **INSTRUCTIONS.md** — Task execution handbook

---

## Using the UI

1. **Enter a URL** in the Analyze bar and click **Analyze**.
2. The orchestrator dispatches tasks to all four agents simultaneously.
3. Watch progress in the **Log Stream** (bottom-left) and **Task Panel** (right sidebar).
4. When all agents finish, click **View Summary** for a synthesized executive briefing.
5. Click any agent card to open a **Chat Drawer** for direct conversation.

### Manual Tasks

Use the Task Panel form to create individual tasks:
1. Write a description in the textarea.
2. Pick an agent from the dropdown.
3. Click **Submit**.

---

## API Reference

| Method   | Path                       | Purpose                              |
|----------|----------------------------|--------------------------------------|
| `GET`    | `/health`                  | Health check                         |
| `GET`    | `/config`                  | Runtime config (target URL)          |
| `GET`    | `/agents`                  | List all agents with status          |
| `GET`    | `/agents/{id}/status`      | Single agent status                  |
| `POST`   | `/tasks`                   | Create a task                        |
| `GET`    | `/tasks`                   | List recent tasks                    |
| `DELETE` | `/tasks/{id}`              | Delete a task                        |
| `POST`   | `/chat/{agent_id}`         | Send a chat message to an agent      |
| `POST`   | `/workflow/analyze`        | Start full 4-agent analysis          |
| `GET`    | `/workflow`                | List recent workflows                |
| `GET`    | `/workflow/{id}`           | Get workflow with synthesis          |
| `WS`     | `/ws/events`               | Real-time event stream               |

### Example: Create a task via curl

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Analyze pricing strategy for https://example.com", "assign_to": "sales"}'
```

### Example: Start a full analysis

```bash
curl -X POST http://localhost:8000/workflow/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

---

## Task Lifecycle

1. **Created** — Task stored in Postgres, pushed to Redis queue `tasks:{agent_id}`
2. **Locked** — Agent pops task, acquires atomic lock (`task:lock:{task_id}`, 600s TTL)
3. **In Progress** — Agent calls LLM with system prompt + task context + prior findings
4. **Completed** — Result stored, cached in Redis (24h), event published
5. **Synthesized** — (Workflow only) When all 4 agents complete, orchestrator produces executive briefing

---

## Adding a New Agent

1. Create `agents/{name}/prompt.md` with the specialist system prompt.
2. Create `.agents/skills/{name}/SKILL.md` and any reference files.
3. Add the agent definition to `agent.yaml`.
4. Add a service block to `docker-compose.yml` (copy an existing agent service).
5. Rebuild: `docker compose up --build`

---

## Scheduled Workflows

Defined in `scheduler.yml`:

| Trigger                    | Schedule              | Description                    |
|----------------------------|-----------------------|--------------------------------|
| `on_demand_company_analysis` | Manual (API)        | Full 4-agent analysis          |
| `daily_watchlist_refresh`  | `0 6 * * *` (6am UTC)| Refresh watched company URLs   |
| `weekly_competitive_scan`  | `0 8 * * 1` (Mon)    | Multi-company competitive scan |
| `url_submitted`            | Event-driven          | Triggered on Redis event       |

---

## Troubleshooting

### Agents show "offline"

- Check agent container logs: `docker compose logs lawyer`
- Verify `ANTHROPIC_API_KEY` or `ANTHROPIC_OAUTH_KEY` is set in `.env`
- Ensure Redis is healthy: `docker compose exec redis redis-cli ping`

### Tasks stuck in "pending"

- The assigned agent may be offline or crashed — check its logs.
- Verify Redis connectivity: `docker compose exec redis redis-cli LLEN tasks:lawyer`

### Database connection errors

- Wait for Postgres healthcheck to pass (can take ~10s on first boot).
- Check credentials in `.env` match `docker-compose.yml`.

### Search channels unavailable

- This is non-fatal — agents work without search but produce less grounded output.
- Configure channels: `docker exec agent-lawyer agent-search configure`
- Check status: `docker exec agent-lawyer agent-search doctor`

### Rebuild from scratch

```bash
docker compose down -v   # removes volumes (data will be lost)
docker compose up --build
```

---

## Project Structure

```
agent-swarm-studio/
├── agents/
│   ├── base/               # Shared agent image (agent_runner.py, Dockerfile)
│   ├── lawyer/prompt.md
│   ├── data-researcher/prompt.md
│   ├── marketing/prompt.md
│   └── sales/prompt.md
├── backend/
│   ├── main.py             # FastAPI app, lifespan, table creation
│   ├── routers/            # tasks, agents, chat, workflow
│   ├── services/           # task_queue, memory helpers
│   └── ws/events.py        # WebSocket + Redis pub/sub bridge
├── proxy/
│   └── claude_proxy.py     # OAuth token proxy (optional)
├── ui/
│   ├── src/                # React components, hooks, api client
│   ├── nginx.conf          # SPA + API proxy
│   └── Dockerfile          # Node build -> nginx serve
├── .agents/skills/         # Per-agent skill definitions + references
├── docker-compose.yml      # Full stack (8 services)
├── agent.yaml              # Agent registry
├── scheduler.yml           # Cron triggers + workflow definitions
├── SOUL.md                 # Shared identity
├── RULES.md                # Operating rules
├── AGENTS.md               # Collaboration protocol
└── INSTRUCTIONS.md         # Task execution handbook
```
