# Agent Hot-Swap from gitagent Registry

**Date**: 2026-04-03
**Status**: Approved
**Author**: Travis Burmaster + Claude

## Summary

Add the ability to replace any existing agent slot (lawyer, data-researcher, marketing, sales) with an agent from the [gitagent registry](https://registry.gitagent.sh). The replacement follows a **hybrid model**: the registry agent's prompt, skills, and metadata replace the original, but swarm-level identity files (SOUL.md, RULES.md, AGENTS.md, INSTRUCTIONS.md), `agent-search-tool` integration, and Docker infrastructure are preserved. Backup and restore are built in for safe rollback.

Both a **UI option** (on each AgentCard) and a **CLI script** are provided.

## Approach

**Hot-Swap with Rollback** — fetch the registry agent definition, back up the current agent's config, write the new files, restart the container. A "Restore Original" action reverts to the backup.

## Design

### 1. Registry Client

A Python module (`backend/services/registry_client.py`) that handles fetching agent definitions from `registry.gitagent.sh`.

**Responsibilities:**

- Parse a registry URL (e.g. `registry.gitagent.sh/agent/shreyas-lyzr/quant-sim`) into `owner` + `agent_name`
- Fetch the agent manifest (name, role, prompt content, skills, capabilities, tags) from the registry API
- Normalize the fetched data into the internal format expected by the swarm
- Return a `RegistryAgent` dataclass with all necessary fields

**URL formats accepted:**

- `https://registry.gitagent.sh/agent/shreyas-lyzr/quant-sim`
- `registry.gitagent.sh/agent/shreyas-lyzr/quant-sim`
- `shreyas-lyzr/quant-sim` (shorthand)

**Error handling:**

- Registry unreachable: return clear error message
- Agent not found (404): return "agent not found in registry"
- Invalid manifest: return validation errors

### 2. Backup & Restore

**Backup location:** `agents/<slot-id>/.backup/`

**Contents:**
- `prompt.md` — the original agent prompt
- `skills/` — copy of the original skill files
- `manifest.json` — metadata:
  ```json
  {
    "original_name": "Corporate Intelligence Lawyer",
    "original_role": "legal",
    "backed_up_at": "2026-04-03T12:00:00Z",
    "replaced_by": {
      "registry_url": "registry.gitagent.sh/agent/shreyas-lyzr/quant-sim",
      "name": "Quant Sim",
      "fetched_at": "2026-04-03T12:00:00Z"
    }
  }
  ```

**Rules:**
- One backup per slot (replacing again overwrites the previous backup)
- Restore copies `.backup/` contents back to the active locations and removes the backup
- Backup is created atomically before any replacement writes

### 3. Backend API

New endpoints added to `backend/routers/agents.py`:

#### `POST /agents/{agent_id}/replace`

```json
{
  "registry_url": "registry.gitagent.sh/agent/shreyas-lyzr/quant-sim"
}
```

Flow:
1. Validate `agent_id` is a known agent slot
2. Fetch agent definition from registry via `RegistryClient`
3. Back up current agent's `prompt.md` and skill files to `agents/<slot>/.backup/`
4. Write new `prompt.md` to `agents/<slot>/prompt.md`
5. Write new skill files to `.agents/skills/<slot>/`
6. Update `agent.yaml` entry for this slot (name, role, capabilities, tags)
7. Restart the agent container (`docker compose restart <slot>`)
8. Return updated agent info + replacement metadata

Response:
```json
{
  "agent_id": "sales",
  "new_name": "Quant Sim",
  "new_role": "quantitative-simulation",
  "registry_url": "registry.gitagent.sh/agent/shreyas-lyzr/quant-sim",
  "backup_exists": true,
  "status": "restarting"
}
```

#### `POST /agents/{agent_id}/restore`

Flow:
1. Check `.backup/` exists for the slot
2. Copy backed-up `prompt.md` and skills back to active locations
3. Restore original `agent.yaml` entry from `manifest.json`
4. Remove `.backup/` directory
5. Restart the agent container
6. Return restored agent info

#### `GET /agents/{agent_id}/replacement-info`

Returns:
```json
{
  "agent_id": "sales",
  "is_replaced": true,
  "registry_url": "registry.gitagent.sh/agent/shreyas-lyzr/quant-sim",
  "replacement_name": "Quant Sim",
  "replaced_at": "2026-04-03T12:00:00Z",
  "backup_exists": true,
  "original_name": "Revenue & Sales Intelligence Agent"
}
```

### 4. UI Changes

#### AgentCard Updates (`ui/src/components/AgentCard.tsx`)

Add a dropdown menu (gear icon or "..." overflow button) to each AgentCard with two actions:

- **"Replace with Registry Agent"** — opens a `ReplaceAgentModal`
- **"Restore Original"** — only visible when `is_replaced` is true; shows confirmation dialog, then calls `POST /agents/{id}/restore`

#### New Component: `ReplaceAgentModal` (`ui/src/components/ReplaceAgentModal.tsx`)

- Text input for registry URL, with placeholder: `e.g. shreyas-lyzr/quant-sim`
- "Replace" button triggers `POST /agents/{id}/replace`
- Loading state while fetching from registry + restarting container
- Success state shows new agent name and "Done" button
- Error state shows error message with retry option

#### Visual Indicator on AgentCard

When an agent slot is running a registry agent:
- Show a small badge below the agent ID with the registry agent name (e.g. "quant-sim")
- Subtle visual cue (e.g. a small swap icon or different border style) to distinguish replaced agents

#### API Client Updates (`ui/src/lib/api.ts`)

Add functions:
```typescript
export const replaceAgent = (agentId: string, registryUrl: string): Promise<ReplaceResult> =>
  api.post(`/agents/${agentId}/replace`, { registry_url: registryUrl }).then(r => r.data);

export const restoreAgent = (agentId: string): Promise<Agent> =>
  api.post(`/agents/${agentId}/restore`).then(r => r.data);

export const getReplacementInfo = (agentId: string): Promise<ReplacementInfo> =>
  api.get(`/agents/${agentId}/replacement-info`).then(r => r.data);
```

### 5. CLI Script

`scripts/replace_agent.py` — standalone CLI for power users:

```bash
# Replace an agent slot with a registry agent
python -m scripts.replace_agent --slot sales --registry shreyas-lyzr/quant-sim

# Restore the original agent
python -m scripts.replace_agent --slot sales --restore

# Show current replacement status
python -m scripts.replace_agent --slot sales --info
```

Reuses `RegistryClient` and backup logic from the backend. Calls `docker compose restart <slot>` after file changes.

### 6. Hybrid Model — What Changes vs. What Stays

| Aspect | Replaced | Kept |
|--------|----------|------|
| `prompt.md` | From registry agent | - |
| Skill files | From registry agent | - |
| Agent name/role/tags | From registry agent | - |
| Capabilities | From registry agent | - |
| SOUL.md | - | Swarm shared |
| RULES.md | - | Swarm shared |
| AGENTS.md | - | Swarm shared |
| INSTRUCTIONS.md | - | Swarm shared |
| `agent-search-tool` | - | Always available |
| Docker infra | - | Same container slot |
| Redis queue | - | Same `tasks:<slot-id>` |
| Postgres connection | - | Same pool |
| `accepts_from` / `delegates_to` | - | Unchanged |
| Model | - | Uses swarm default |

The registry agent becomes a specialist in the swarm — it brings its own expertise but operates under the team's shared values, rules, and collaboration protocol.

### 7. File Changes Summary

**New files:**
- `backend/services/registry_client.py` — registry fetch + URL parsing
- `backend/services/agent_swap.py` — backup, replace, restore logic
- `ui/src/components/ReplaceAgentModal.tsx` — replacement UI modal
- `scripts/replace_agent.py` — CLI tool

**Modified files:**
- `backend/routers/agents.py` — add 3 new endpoints
- `ui/src/components/AgentCard.tsx` — add dropdown menu + replacement badge
- `ui/src/lib/api.ts` — add API client functions + types
- `backend/requirements.txt` — add `docker` package (for container restart via API, if needed)

### 8. Open Questions

- **Registry API shape**: The exact API endpoints and response format from `registry.gitagent.sh` need to be confirmed. The `RegistryClient` will be built with a clear interface so the fetch logic can be adapted once the API is known.
- **Container restart method**: Either shell out to `docker compose restart <slot>` or use the Docker SDK (`docker` Python package). Docker SDK is cleaner but adds a dependency. Initial implementation will use subprocess + `docker compose restart` for simplicity.
