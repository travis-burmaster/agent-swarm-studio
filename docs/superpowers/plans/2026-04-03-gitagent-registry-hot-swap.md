# gitagent Registry Agent Hot-Swap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable replacing any agent slot with a registry agent from gitagent, with backup/restore and both UI + CLI interfaces.

**Architecture:** Backend service fetches agent definitions from `registry.gitagent.sh`, backs up the current agent's prompt + skills, writes the replacement files, and restarts the container. The UI adds a dropdown menu on each AgentCard with "Replace" and "Restore" actions.

**Tech Stack:** Python/FastAPI (backend), httpx (registry fetch), React/TypeScript (UI), Docker Compose (container restart)

**Spec:** `docs/superpowers/specs/2026-04-03-gitagent-registry-hot-swap-design.md`

---

## File Structure

**New files:**
| File | Responsibility |
|------|---------------|
| `backend/services/registry_client.py` | Fetch + parse agent definitions from gitagent registry |
| `backend/services/agent_swap.py` | Backup, replace, and restore agent slot files + config |
| `ui/src/components/ReplaceAgentModal.tsx` | Modal UI for entering registry URL and triggering replacement |
| `scripts/replace_agent.py` | CLI tool for replace/restore/info operations |

**Modified files:**
| File | Changes |
|------|---------|
| `backend/routers/agents.py` | Add 3 endpoints: replace, restore, replacement-info |
| `ui/src/lib/api.ts` | Add types + API functions for replace/restore/info |
| `ui/src/components/AgentCard.tsx` | Add dropdown menu with Replace/Restore actions + registry badge |
| `ui/src/components/AgentBoard.tsx` | Pass `onReplace`/`onRestore` callbacks to AgentCard |
| `ui/src/App.tsx` | Add ReplaceAgentModal state + pass handlers to AgentBoard |

---

### Task 1: Registry Client

**Files:**
- Create: `backend/services/registry_client.py`

- [ ] **Step 1: Create the registry client module**

```python
"""Registry client — fetch agent definitions from gitagent registry."""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class RegistryAgent:
    """Normalized agent definition from the gitagent registry."""
    owner: str
    name: str
    display_name: str
    role: str
    description: str
    prompt_content: str
    skills: list[dict] = field(default_factory=list)  # [{"name": str, "content": str}]
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_url: str = ""


def parse_registry_url(url: str) -> tuple[str, str]:
    """
    Parse a gitagent registry URL into (owner, agent_name).

    Accepts:
      - https://registry.gitagent.sh/agent/owner/name
      - registry.gitagent.sh/agent/owner/name
      - owner/name
    """
    url = url.strip().rstrip("/")

    # Strip protocol
    url = re.sub(r"^https?://", "", url)

    # Strip registry domain + /agent/ prefix
    url = re.sub(r"^registry\.gitagent\.sh/agent/", "", url)

    parts = url.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid registry URL. Expected format: 'owner/agent-name' or "
            f"'registry.gitagent.sh/agent/owner/agent-name'. Got: '{url}'"
        )
    return parts[0], parts[1]


async def fetch_registry_agent(registry_url: str) -> RegistryAgent:
    """
    Fetch an agent definition from the gitagent registry.

    Args:
        registry_url: Registry URL in any accepted format.

    Returns:
        RegistryAgent with all fields populated.

    Raises:
        ValueError: If the URL is malformed.
        httpx.HTTPStatusError: If the registry returns an error.
        httpx.ConnectError: If the registry is unreachable.
    """
    owner, agent_name = parse_registry_url(registry_url)
    api_url = f"https://registry.gitagent.sh/api/v1/agents/{owner}/{agent_name}"
    canonical_url = f"https://registry.gitagent.sh/agent/{owner}/{agent_name}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

    # Normalize registry response into our internal format
    agent_data = data if "agent" not in data else data["agent"]

    # Fetch prompt content if it's a URL reference
    prompt_content = agent_data.get("prompt", "") or agent_data.get("prompt_content", "")
    prompt_url = agent_data.get("prompt_url", "")
    if prompt_url and not prompt_content:
        async with httpx.AsyncClient(timeout=30.0) as client:
            prompt_resp = await client.get(prompt_url)
            prompt_resp.raise_for_status()
            prompt_content = prompt_resp.text

    # Fetch skill contents if they are URL references
    skills = []
    for skill in agent_data.get("skills", []):
        if isinstance(skill, str):
            # skill is a URL — fetch it
            async with httpx.AsyncClient(timeout=30.0) as client:
                skill_resp = await client.get(skill)
                skill_resp.raise_for_status()
                skill_name = skill.rsplit("/", 1)[-1]
                skills.append({"name": skill_name, "content": skill_resp.text})
        elif isinstance(skill, dict):
            skills.append({
                "name": skill.get("name", "SKILL.md"),
                "content": skill.get("content", ""),
            })

    return RegistryAgent(
        owner=owner,
        name=agent_name,
        display_name=agent_data.get("name", agent_name),
        role=agent_data.get("role", agent_name),
        description=agent_data.get("description", ""),
        prompt_content=prompt_content,
        skills=skills,
        capabilities=agent_data.get("capabilities", []),
        tags=agent_data.get("tags", []),
        source_url=canonical_url,
    )
```

- [ ] **Step 2: Verify the module loads without import errors**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio && python -c "from backend.services.registry_client import parse_registry_url, RegistryAgent; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/registry_client.py
git commit -m "feat: add gitagent registry client for fetching agent definitions"
```

---

### Task 2: Agent Swap Service

**Files:**
- Create: `backend/services/agent_swap.py`

- [ ] **Step 1: Create the agent swap service**

```python
"""Agent swap service — backup, replace, and restore agent slots."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from services.registry_client import RegistryAgent

# Paths relative to the project root (mapped via Docker volumes or local dev)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # agent-swarm-studio/


def _agents_dir(slot_id: str) -> Path:
    return PROJECT_ROOT / "agents" / slot_id


def _skills_dir(slot_id: str) -> Path:
    return PROJECT_ROOT / ".agents" / "skills" / slot_id


def _backup_dir(slot_id: str) -> Path:
    return _agents_dir(slot_id) / ".backup"


def _manifest_path(slot_id: str) -> Path:
    return _backup_dir(slot_id) / "manifest.json"


def _agent_yaml_path() -> Path:
    return PROJECT_ROOT / "agent.yaml"


VALID_SLOTS = {"lawyer", "data-researcher", "marketing", "sales"}


def validate_slot(slot_id: str) -> None:
    if slot_id not in VALID_SLOTS:
        raise ValueError(f"Unknown agent slot '{slot_id}'. Valid slots: {', '.join(sorted(VALID_SLOTS))}")


def get_replacement_info(slot_id: str) -> dict:
    """Return replacement status for an agent slot."""
    validate_slot(slot_id)
    manifest_path = _manifest_path(slot_id)
    if not manifest_path.exists():
        return {
            "agent_id": slot_id,
            "is_replaced": False,
            "registry_url": None,
            "replacement_name": None,
            "replaced_at": None,
            "backup_exists": False,
            "original_name": None,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replaced_by = manifest.get("replaced_by", {})
    return {
        "agent_id": slot_id,
        "is_replaced": True,
        "registry_url": replaced_by.get("registry_url"),
        "replacement_name": replaced_by.get("name"),
        "replaced_at": replaced_by.get("fetched_at"),
        "backup_exists": True,
        "original_name": manifest.get("original_name"),
    }


def backup_agent(slot_id: str) -> None:
    """Back up the current agent's prompt and skills before replacement."""
    validate_slot(slot_id)
    backup = _backup_dir(slot_id)

    # Remove previous backup if it exists
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)

    # Back up prompt.md
    prompt_src = _agents_dir(slot_id) / "prompt.md"
    if prompt_src.exists():
        shutil.copy2(prompt_src, backup / "prompt.md")

    # Back up skills
    skills_src = _skills_dir(slot_id)
    if skills_src.exists():
        shutil.copytree(skills_src, backup / "skills")


def write_manifest(slot_id: str, original_name: str, original_role: str, registry_agent: RegistryAgent) -> None:
    """Write the backup manifest with metadata about the replacement."""
    manifest = {
        "original_name": original_name,
        "original_role": original_role,
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "replaced_by": {
            "registry_url": registry_agent.source_url,
            "name": registry_agent.display_name,
            "owner": registry_agent.owner,
            "agent_name": registry_agent.name,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    _manifest_path(slot_id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def replace_agent_files(slot_id: str, registry_agent: RegistryAgent) -> None:
    """Write the registry agent's prompt and skills to the agent slot."""
    validate_slot(slot_id)

    # Write new prompt.md
    prompt_dest = _agents_dir(slot_id) / "prompt.md"
    prompt_dest.write_text(registry_agent.prompt_content, encoding="utf-8")

    # Write new skills
    skills_dest = _skills_dir(slot_id)
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    skills_dest.mkdir(parents=True, exist_ok=True)

    for skill in registry_agent.skills:
        skill_file = skills_dest / skill["name"]
        skill_file.write_text(skill["content"], encoding="utf-8")

    # If no skills provided by registry, write a minimal SKILL.md
    if not registry_agent.skills:
        (skills_dest / "SKILL.md").write_text(
            f"# {registry_agent.display_name}\n\n{registry_agent.description}\n",
            encoding="utf-8",
        )


def update_agent_yaml(slot_id: str, registry_agent: RegistryAgent) -> dict:
    """
    Update the agent.yaml entry for this slot with registry agent metadata.
    Returns the original agent config for the slot (before update).
    """
    yaml_path = _agent_yaml_path()
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    agents = config.get("agents", [])
    original = None
    for agent in agents:
        if agent["id"] == slot_id:
            original = {
                "name": agent.get("name", ""),
                "role": agent.get("role", ""),
                "capabilities": agent.get("capabilities", []),
                "tags": agent.get("tags", []),
            }
            # Update with registry agent data
            agent["name"] = registry_agent.display_name
            agent["role"] = registry_agent.role
            if registry_agent.capabilities:
                agent["capabilities"] = registry_agent.capabilities
            if registry_agent.tags:
                agent["tags"] = registry_agent.tags
            break

    if original is None:
        raise ValueError(f"Agent '{slot_id}' not found in agent.yaml")

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return original


def restore_agent(slot_id: str) -> dict:
    """
    Restore the original agent from backup.
    Returns the manifest data of what was restored.
    """
    validate_slot(slot_id)
    backup = _backup_dir(slot_id)
    manifest_path = _manifest_path(slot_id)

    if not manifest_path.exists():
        raise FileNotFoundError(f"No backup found for agent '{slot_id}'")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Restore prompt.md
    backup_prompt = backup / "prompt.md"
    if backup_prompt.exists():
        shutil.copy2(backup_prompt, _agents_dir(slot_id) / "prompt.md")

    # Restore skills
    backup_skills = backup / "skills"
    skills_dest = _skills_dir(slot_id)
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    if backup_skills.exists():
        shutil.copytree(backup_skills, skills_dest)

    # Restore agent.yaml entry
    yaml_path = _agent_yaml_path()
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        if agent["id"] == slot_id:
            agent["name"] = manifest["original_name"]
            agent["role"] = manifest["original_role"]
            break

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Remove backup
    shutil.rmtree(backup)

    return manifest


def restart_agent_container(slot_id: str) -> None:
    """Restart the agent's Docker container via docker compose."""
    subprocess.run(
        ["docker", "compose", "restart", slot_id],
        cwd=str(PROJECT_ROOT),
        check=True,
        capture_output=True,
        timeout=60,
    )
```

- [ ] **Step 2: Verify the module loads**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio && python -c "from backend.services.agent_swap import validate_slot, VALID_SLOTS; print('OK', VALID_SLOTS)"`
Expected: `OK {'lawyer', 'data-researcher', 'marketing', 'sales'}`

- [ ] **Step 3: Commit**

```bash
git add backend/services/agent_swap.py
git commit -m "feat: add agent swap service with backup, replace, and restore"
```

---

### Task 3: Backend API Endpoints

**Files:**
- Modify: `backend/routers/agents.py`

- [ ] **Step 1: Add the three new endpoints to agents.py**

Add these imports at the top of `backend/routers/agents.py`:

```python
import logging
from pydantic import BaseModel

from services.registry_client import fetch_registry_agent
from services.agent_swap import (
    backup_agent,
    get_replacement_info,
    replace_agent_files,
    restart_agent_container,
    restore_agent,
    update_agent_yaml,
    validate_slot,
    write_manifest,
)
```

Add a logger after the imports:

```python
logger = logging.getLogger(__name__)
```

Add a request model:

```python
class ReplaceRequest(BaseModel):
    registry_url: str
```

Add these three endpoints after the existing `get_agent_status` endpoint:

```python
@router.post("/{agent_id}/replace")
async def replace_agent_endpoint(agent_id: str, body: ReplaceRequest, request: Request):
    """Replace an agent slot with an agent from the gitagent registry."""
    try:
        validate_slot(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        # Fetch from registry
        registry_agent = await fetch_registry_agent(body.registry_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from registry: {e}")

    # Get current agent info for backup
    config = request.app.state.agents_config
    agent_cfg = next((a for a in config.get("agents", []) if a["id"] == agent_id), None)
    if not agent_cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in config")

    original_name = agent_cfg.get("name", "")
    original_role = agent_cfg.get("role", "")

    # Backup current agent
    backup_agent(agent_id)
    write_manifest(agent_id, original_name, original_role, registry_agent)

    # Replace files + update config
    replace_agent_files(agent_id, registry_agent)
    update_agent_yaml(agent_id, registry_agent)

    # Update in-memory config to reflect the change
    for a in config.get("agents", []):
        if a["id"] == agent_id:
            a["name"] = registry_agent.display_name
            a["role"] = registry_agent.role
            if registry_agent.capabilities:
                a["capabilities"] = registry_agent.capabilities
            if registry_agent.tags:
                a["tags"] = registry_agent.tags
            break

    # Restart container
    try:
        restart_agent_container(agent_id)
    except Exception as e:
        logger.warning("Container restart failed (may need manual restart): %s", e)

    return {
        "agent_id": agent_id,
        "new_name": registry_agent.display_name,
        "new_role": registry_agent.role,
        "registry_url": registry_agent.source_url,
        "backup_exists": True,
        "status": "restarting",
    }


@router.post("/{agent_id}/restore")
async def restore_agent_endpoint(agent_id: str, request: Request):
    """Restore the original agent from backup."""
    try:
        validate_slot(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        manifest = restore_agent(agent_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Update in-memory config
    config = request.app.state.agents_config
    for a in config.get("agents", []):
        if a["id"] == agent_id:
            a["name"] = manifest["original_name"]
            a["role"] = manifest["original_role"]
            break

    # Restart container
    try:
        restart_agent_container(agent_id)
    except Exception as e:
        logger.warning("Container restart failed (may need manual restart): %s", e)

    return {
        "agent_id": agent_id,
        "restored_name": manifest["original_name"],
        "restored_role": manifest["original_role"],
        "status": "restarting",
    }


@router.get("/{agent_id}/replacement-info")
async def get_replacement_info_endpoint(agent_id: str):
    """Check if an agent slot has been replaced and get metadata."""
    try:
        return get_replacement_info(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 2: Verify the backend starts without errors**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/backend && python -c "from routers.agents import router; print('Routes:', [r.path for r in router.routes])"`
Expected: Should list all routes including the three new ones.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/agents.py
git commit -m "feat: add replace, restore, and replacement-info API endpoints"
```

---

### Task 4: Frontend API Client

**Files:**
- Modify: `ui/src/lib/api.ts`

- [ ] **Step 1: Add types and API functions**

Add these types after the existing `Agent` interface in `ui/src/lib/api.ts`:

```typescript
// ── Replacement types ────────────────────────────────────────────────────────

export interface ReplaceResult {
  agent_id: string;
  new_name: string;
  new_role: string;
  registry_url: string;
  backup_exists: boolean;
  status: string;
}

export interface RestoreResult {
  agent_id: string;
  restored_name: string;
  restored_role: string;
  status: string;
}

export interface ReplacementInfo {
  agent_id: string;
  is_replaced: boolean;
  registry_url: string | null;
  replacement_name: string | null;
  replaced_at: string | null;
  backup_exists: boolean;
  original_name: string | null;
}
```

Add these API functions after the existing `getConfig` function, before `export default api`:

```typescript
// ── Agent replacement functions ──────────────────────────────────────────────

export const replaceAgent = (
  agentId: string,
  registryUrl: string
): Promise<ReplaceResult> =>
  api
    .post<ReplaceResult>(`/agents/${agentId}/replace`, {
      registry_url: registryUrl,
    })
    .then((r) => r.data);

export const restoreAgent = (agentId: string): Promise<RestoreResult> =>
  api.post<RestoreResult>(`/agents/${agentId}/restore`).then((r) => r.data);

export const getReplacementInfo = (
  agentId: string
): Promise<ReplacementInfo> =>
  api
    .get<ReplacementInfo>(`/agents/${agentId}/replacement-info`)
    .then((r) => r.data);
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to api.ts

- [ ] **Step 3: Commit**

```bash
git add ui/src/lib/api.ts
git commit -m "feat: add replace/restore/info API client functions"
```

---

### Task 5: ReplaceAgentModal Component

**Files:**
- Create: `ui/src/components/ReplaceAgentModal.tsx`

- [ ] **Step 1: Create the modal component**

```tsx
import React, { useState } from "react";
import { replaceAgent, ReplaceResult } from "../lib/api";

interface ReplaceAgentModalProps {
  agentId: string;
  agentName: string;
  onClose: () => void;
  onReplaced: (result: ReplaceResult) => void;
}

export default function ReplaceAgentModal({
  agentId,
  agentName,
  onClose,
  onReplaced,
}: ReplaceAgentModalProps) {
  const [registryUrl, setRegistryUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReplaceResult | null>(null);

  const handleReplace = async () => {
    const url = registryUrl.trim();
    if (!url || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await replaceAgent(agentId, url);
      setResult(res);
      onReplaced(res);
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail || err?.message || "Failed to replace agent";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-xl w-full max-w-md p-6">
        <h2 className="text-white font-semibold text-sm mb-1">
          Replace Agent: <span className="text-indigo-400">{agentName}</span>
        </h2>
        <p className="text-muted text-xs mb-4">
          Slot: <code className="text-gray-400">{agentId}</code> — the current
          agent will be backed up and can be restored later.
        </p>

        {result ? (
          /* Success state */
          <div>
            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-3 mb-4">
              <p className="text-green-300 text-sm font-medium">
                Replaced with {result.new_name}
              </p>
              <p className="text-green-400/70 text-xs mt-1">
                Role: {result.new_role} — container is restarting
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium py-2 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          /* Input state */
          <div>
            <label className="text-xs text-muted block mb-1">
              gitagent Registry URL
            </label>
            <input
              type="text"
              value={registryUrl}
              onChange={(e) => setRegistryUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleReplace();
              }}
              placeholder="e.g. shreyas-lyzr/quant-sim"
              className="w-full bg-black/40 border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-muted focus:outline-none focus:border-indigo-500 transition-colors mb-3"
              disabled={loading}
              autoFocus
            />

            {error && (
              <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-2 mb-3">
                <p className="text-red-300 text-xs">{error}</p>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={onClose}
                disabled={loading}
                className="flex-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleReplace}
                disabled={loading || !registryUrl.trim()}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Replacing...
                  </>
                ) : (
                  "Replace"
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/ReplaceAgentModal.tsx
git commit -m "feat: add ReplaceAgentModal component"
```

---

### Task 6: Update AgentCard with Dropdown Menu

**Files:**
- Modify: `ui/src/components/AgentCard.tsx`

- [ ] **Step 1: Rewrite AgentCard with dropdown menu and registry badge**

Replace the full contents of `ui/src/components/AgentCard.tsx` with:

```tsx
import React, { useEffect, useRef, useState } from "react";
import { Agent, getReplacementInfo, ReplacementInfo } from "../lib/api";

interface AgentCardProps {
  agent: Agent;
  onClick: () => void;
  onReplace: (agent: Agent) => void;
  onRestore: (agentId: string) => void;
}

function StatusDot({ status }: { status: Agent["status"] }) {
  const colors: Record<Agent["status"], string> = {
    idle: "bg-green-500",
    working: "bg-yellow-400 animate-pulse",
    error: "bg-red-500",
    offline: "bg-gray-600",
  };
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status] ?? "bg-gray-600"}`}
      title={status}
    />
  );
}

export default function AgentCard({ agent, onClick, onReplace, onRestore }: AgentCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [replacementInfo, setReplacementInfo] = useState<ReplacementInfo | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Fetch replacement info on mount
  useEffect(() => {
    getReplacementInfo(agent.id)
      .then(setReplacementInfo)
      .catch(() => {});
  }, [agent.id]);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const isReplaced = replacementInfo?.is_replaced ?? false;

  return (
    <div className="relative">
      <button
        onClick={onClick}
        className="text-left w-full bg-card border border-border rounded-xl p-4 hover:border-gray-600 hover:bg-[#181818] transition-all duration-150 flex flex-col gap-2"
        style={{ borderLeftColor: agent.color, borderLeftWidth: "3px" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs text-muted uppercase tracking-widest">
            {agent.id}
          </span>
          <div className="flex items-center gap-2">
            <span
              onClick={(e) => { e.stopPropagation(); onClick(); }}
              className="text-[10px] text-indigo-400 hover:text-indigo-300 cursor-pointer transition-colors border border-indigo-500/50 hover:border-indigo-400 rounded px-1.5 py-0.5"
            >
              Chat
            </span>
            {/* Dropdown trigger */}
            <span
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((prev) => !prev);
              }}
              className="text-[10px] text-gray-400 hover:text-white cursor-pointer transition-colors border border-border hover:border-gray-500 rounded px-1.5 py-0.5"
              title="Agent options"
            >
              ...
            </span>
            <StatusDot status={agent.status} />
          </div>
        </div>

        {/* Role */}
        <div className="font-semibold text-white text-sm leading-tight">
          {agent.role}
        </div>

        {/* Registry badge */}
        {isReplaced && replacementInfo?.replacement_name && (
          <div className="flex items-center gap-1">
            <span className="text-[9px] bg-purple-900/50 text-purple-300 border border-purple-700/50 rounded px-1.5 py-0.5 font-mono">
              registry: {replacementInfo.replacement_name}
            </span>
          </div>
        )}

        {/* Current task */}
        {agent.current_task && (
          <div className="text-xs text-yellow-400 truncate" title={agent.current_task}>
            {agent.current_task}
          </div>
        )}

        {/* Last output */}
        {agent.last_output && !agent.current_task && (
          <div className="text-xs text-muted line-clamp-2" title={agent.last_output}>
            {agent.last_output}
          </div>
        )}

        {/* Status badge */}
        <div className="mt-auto pt-1">
          <span
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wide ${
              agent.status === "working"
                ? "bg-yellow-900/50 text-yellow-300"
                : agent.status === "error"
                ? "bg-red-900/50 text-red-300"
                : agent.status === "idle"
                ? "bg-green-900/50 text-green-300"
                : "bg-gray-800 text-gray-500"
            }`}
          >
            {agent.status}
          </span>
        </div>
      </button>

      {/* Dropdown menu */}
      {menuOpen && (
        <div
          ref={menuRef}
          className="absolute right-2 top-10 z-20 bg-[#1a1a1a] border border-border rounded-lg shadow-xl py-1 min-w-[180px]"
        >
          <button
            onClick={() => {
              setMenuOpen(false);
              onReplace(agent);
            }}
            className="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
          >
            Replace with Registry Agent
          </button>
          {isReplaced && (
            <button
              onClick={() => {
                setMenuOpen(false);
                onRestore(agent.id);
              }}
              className="w-full text-left px-3 py-2 text-xs text-amber-400 hover:bg-white/5 hover:text-amber-300 transition-colors"
            >
              Restore Original
            </button>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: Errors about missing `onReplace`/`onRestore` props in AgentBoard.tsx and App.tsx (expected — we fix those next)

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/AgentCard.tsx
git commit -m "feat: add dropdown menu and registry badge to AgentCard"
```

---

### Task 7: Wire Up AgentBoard, App, and Modal

**Files:**
- Modify: `ui/src/components/AgentBoard.tsx`
- Modify: `ui/src/App.tsx`

- [ ] **Step 1: Update AgentBoard to pass replace/restore callbacks**

Replace the full contents of `ui/src/components/AgentBoard.tsx` with:

```tsx
import React from "react";
import { Agent } from "../lib/api";
import AgentCard from "./AgentCard";

interface AgentBoardProps {
  agents: Agent[];
  onSelectAgent: (agent: Agent) => void;
  onReplace: (agent: Agent) => void;
  onRestore: (agentId: string) => void;
}

export default function AgentBoard({ agents, onSelectAgent, onReplace, onRestore }: AgentBoardProps) {
  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-widest text-muted mb-3">
        Agents
      </h2>
      {agents.length === 0 ? (
        <div className="text-muted text-sm py-8 text-center border border-border rounded-xl">
          No agents configured. Check your <code className="text-gray-400">agents.yaml</code>.
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onClick={() => onSelectAgent(agent)}
              onReplace={onReplace}
              onRestore={onRestore}
            />
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Update App.tsx to manage replace modal state**

Add the import for `ReplaceAgentModal` and `restoreAgent` at the top of `App.tsx`:

```typescript
import ReplaceAgentModal from "./components/ReplaceAgentModal";
import { Agent, Task, startAnalysis, askAllAgents, getConfig, restoreAgent } from "./lib/api";
```

Add state variables inside the `App` component (after the existing state):

```typescript
const [replaceTarget, setReplaceTarget] = useState<Agent | null>(null);
```

Add the restore handler (after `handleAskAll`):

```typescript
const handleRestore = async (agentId: string) => {
  if (!confirm(`Restore the original agent for slot "${agentId}"?`)) return;
  try {
    await restoreAgent(agentId);
    await refreshAgents();
  } catch (err) {
    console.error("Restore failed:", err);
  }
};
```

Update the `<AgentBoard>` JSX to pass the new props:

```tsx
<AgentBoard
  agents={agents}
  onSelectAgent={setSelectedAgent}
  onReplace={setReplaceTarget}
  onRestore={handleRestore}
/>
```

Add the modal before the closing `</div>` of the root element (after the ChatDrawer block):

```tsx
{replaceTarget && (
  <ReplaceAgentModal
    agentId={replaceTarget.id}
    agentName={replaceTarget.role || replaceTarget.id}
    onClose={() => setReplaceTarget(null)}
    onReplaced={() => {
      setReplaceTarget(null);
      refreshAgents();
    }}
  />
)}
```

- [ ] **Step 3: Verify TypeScript compiles cleanly**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/ui && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/AgentBoard.tsx ui/src/App.tsx
git commit -m "feat: wire up replace/restore flow in AgentBoard and App"
```

---

### Task 8: CLI Script

**Files:**
- Create: `scripts/replace_agent.py`

- [ ] **Step 1: Create the CLI script**

```python
#!/usr/bin/env python3
"""CLI tool for replacing/restoring agent slots from the gitagent registry.

Usage:
  python -m scripts.replace_agent --slot sales --registry shreyas-lyzr/quant-sim
  python -m scripts.replace_agent --slot sales --restore
  python -m scripts.replace_agent --slot sales --info
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from services.agent_swap import (
    backup_agent,
    get_replacement_info,
    replace_agent_files,
    restart_agent_container,
    restore_agent,
    update_agent_yaml,
    validate_slot,
    write_manifest,
)
from services.registry_client import fetch_registry_agent


async def do_replace(slot: str, registry_url: str) -> None:
    print(f"Fetching agent from registry: {registry_url}")
    registry_agent = await fetch_registry_agent(registry_url)
    print(f"  Found: {registry_agent.display_name} ({registry_agent.role})")

    # Get original info from agent.yaml
    import yaml
    from services.agent_swap import _agent_yaml_path
    with open(_agent_yaml_path()) as f:
        config = yaml.safe_load(f)
    agent_cfg = next((a for a in config.get("agents", []) if a["id"] == slot), None)
    if not agent_cfg:
        print(f"Error: agent '{slot}' not found in agent.yaml")
        sys.exit(1)

    original_name = agent_cfg.get("name", "")
    original_role = agent_cfg.get("role", "")

    print(f"Backing up current agent: {original_name}")
    backup_agent(slot)
    write_manifest(slot, original_name, original_role, registry_agent)

    print("Writing replacement files...")
    replace_agent_files(slot, registry_agent)
    update_agent_yaml(slot, registry_agent)

    print(f"Restarting container: {slot}")
    try:
        restart_agent_container(slot)
        print("Done! Container is restarting.")
    except Exception as e:
        print(f"Warning: container restart failed ({e}). You may need to restart manually:")
        print(f"  docker compose restart {slot}")


def do_restore(slot: str) -> None:
    info = get_replacement_info(slot)
    if not info["is_replaced"]:
        print(f"Agent '{slot}' has not been replaced — nothing to restore.")
        return

    print(f"Restoring original agent: {info['original_name']}")
    restore_agent(slot)

    print(f"Restarting container: {slot}")
    try:
        restart_agent_container(slot)
        print("Done! Original agent restored and container is restarting.")
    except Exception as e:
        print(f"Warning: container restart failed ({e}). Restart manually:")
        print(f"  docker compose restart {slot}")


def do_info(slot: str) -> None:
    info = get_replacement_info(slot)
    print(json.dumps(info, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Replace or restore agent slots from gitagent registry")
    parser.add_argument("--slot", required=True, help="Agent slot ID (lawyer, data-researcher, marketing, sales)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--registry", help="Registry agent reference (e.g. shreyas-lyzr/quant-sim)")
    group.add_argument("--restore", action="store_true", help="Restore the original agent from backup")
    group.add_argument("--info", action="store_true", help="Show replacement status")
    args = parser.parse_args()

    try:
        validate_slot(args.slot)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.registry:
        asyncio.run(do_replace(args.slot, args.registry))
    elif args.restore:
        do_restore(args.slot)
    elif args.info:
        do_info(args.slot)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script loads**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio && python scripts/replace_agent.py --help`
Expected: Prints usage/help text

- [ ] **Step 3: Commit**

```bash
git add scripts/replace_agent.py
git commit -m "feat: add CLI script for agent slot replace/restore"
```

---

### Task 9: Final Integration Verification

- [ ] **Step 1: Verify backend imports**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/backend && python -c "from routers.agents import router; print('Backend OK')"`
Expected: `Backend OK`

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio/ui && npx tsc --noEmit --pretty`
Expected: No errors

- [ ] **Step 3: Verify CLI**

Run: `cd /Users/travisburmaster/git/agent-swarm-studio && python scripts/replace_agent.py --slot sales --info`
Expected: JSON output showing `is_replaced: false`

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: integration fixes for agent hot-swap feature"
```
