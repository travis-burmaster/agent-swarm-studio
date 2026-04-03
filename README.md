# Agent Swarm Studio

Agent Swarm Studio is a visual platform for orchestrating collaborative AI agent swarms across Docker containers — giving teams a real-time dashboard to define agent roles, dispatch tasks, monitor progress, and chat directly with individual agents, all backed by a FastAPI event bus, Redis queues, and Postgres persistent memory.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser UI (React)                       │
│   AgentBoard │ TaskPanel │ ChatDrawer │ LogStream (WebSocket)    │
└────────────────────────────┬────────────────────────────────────┘
                             │  HTTP REST + WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI / Python)                      │
│  /agents  │  /tasks  │  /chat  │  /ws/events  │  /health        │
└──────┬──────────────────────────────────────┬───────────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────┐                    ┌──────────────────┐
│    Redis 7   │                    │  PostgreSQL 16    │
│  Task queues │                    │  memory / tasks   │
│  Pub/Sub     │                    │  chat_messages    │
│  Agent state │                    └──────────────────┘
└──────┬───────┘
       │  brpop / publish
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Containers                            │
│  ┌────────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  orchestrator  │  │  coder   │  │ reviewer │  │  tester  │ │
│  │  (Architect)   │  │ (Senior  │  │  (Code   │  │   (QA    │ │
│  │                │  │  Eng.)   │  │ Review)  │  │  Eng.)   │ │
│  └────────────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/agent-swarm-studio.git
cd agent-swarm-studio

# 2. Configure environment
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and OPENAI_API_KEY

# 3. Launch the full stack
docker compose up --build

# UI  → http://localhost:3000
# API → http://localhost:8000/docs
```

## agents.yaml Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Unique agent identifier (used as Redis queue name and Docker service name) |
| `role` | string | ✅ | Human-readable role title shown in the UI |
| `goal` | string | ✅ | One-sentence mission statement injected into system prompt |
| `model` | string | ✅ | Model identifier (`anthropic/claude-*`, `openai/gpt-*`, etc.) |
| `memory` | boolean | ❌ | Enable persistent memory via Postgres (default: false) |
| `tools` | list[string] | ❌ | Tool names the agent may invoke (informational — enforced by runner) |
| `color` | string | ❌ | Hex color for UI card accent (e.g. `"#6366f1"`) |
| `memory.short_term` | string | ❌ | Redis URL for ephemeral state |
| `memory.long_term` | string | ❌ | Postgres DSN for persistent memory |
| `memory.shared_workspace` | string | ❌ | Filesystem path shared across all agent containers |
| `tasks.process` | string | ❌ | Task routing strategy: `hierarchical` or `parallel` |
| `tasks.max_concurrent` | int | ❌ | Maximum tasks running simultaneously across swarm |
| `tasks.timeout_per_agent` | int | ❌ | Seconds before a task is considered timed out |

## Roadmap

- **MCP tool integration** — plug any Model Context Protocol server into agent tool configs
- **Agent spawning via UI** — define and launch new agents at runtime without restarting the stack
- **Streaming git diffs** — live WebSocket feed of agent-generated code changes with syntax highlighting
- **Multi-project support** — namespace workspaces per project with isolated queues and memory pools
- **Agent-to-agent messaging** — direct message channels between agents for richer collaboration patterns
- **Approval workflows** — human-in-the-loop gates before reviewer approvals propagate downstream
- **Cost tracking** — per-agent token usage dashboard with budget alerts

## License

MIT © 2025 Agent Swarm Studio Contributors
