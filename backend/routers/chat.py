"""Chat router — direct conversations with individual agents."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import anthropic
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.post("/{agent_id}", response_model=Dict[str, Any])
async def chat_with_agent(agent_id: str, body: ChatMessage, request: Request):
    """
    Chat with a specific agent.  Loads recent history from Postgres,
    calls Anthropic claude-haiku-4-5, stores both turns, publishes event.
    """
    config = request.app.state.agents_config
    agents = config.get("agents", [])
    agent_cfg = next((a for a in agents if a["id"] == agent_id), None)
    if not agent_cfg and agent_id == "orchestrator":
        agent_cfg = {
            "id": "orchestrator",
            "name": "Orchestrator",
            "role": "strategic synthesizer across all agents",
        }
    if not agent_cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    db = request.app.state.db
    redis = request.app.state.redis
    now = datetime.now(timezone.utc)

    # ── Load recent completed tasks from ALL agents in the swarm ─────
    task_rows = await db.fetch(
        """
        SELECT assign_to, description, result, updated_at FROM tasks
        WHERE status = 'completed' AND result IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 10
        """,
    )
    task_context = ""
    if task_rows:
        own_parts = []
        other_parts = []
        for tr in reversed(task_rows):
            ts = tr["updated_at"].strftime("%Y-%m-%d %H:%M UTC") if tr["updated_at"] else ""
            agent = tr["assign_to"]
            entry = (
                f"### [{agent}] Task: {tr['description']}\n"
                f"Completed: {ts}\n"
                f"{tr['result'][:3000]}"
            )
            if agent == agent_id:
                own_parts.append(entry)
            else:
                other_parts.append(entry)

        sections = []
        if own_parts:
            sections.append(
                "## Your Completed Task Results\n\n" + "\n\n---\n\n".join(own_parts)
            )
        if other_parts:
            sections.append(
                "## Other Agents' Task Results (cross-agent context)\n\n"
                + "\n\n---\n\n".join(other_parts)
            )
        if sections:
            task_context = "\n\n" + "\n\n".join(sections)

    # ── Load last 20 messages from Postgres ──────────────────────────
    rows = await db.fetch(
        """
        SELECT role, content FROM chat_messages
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        agent_id,
    )
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # Append current user message
    history.append({"role": "user", "content": body.message})

    # ── Call Anthropic (proxy or direct) ────────────────────────────
    oauth_key = os.getenv("ANTHROPIC_OAUTH_KEY", "").strip()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    proxy_url = os.getenv("CLAUDE_PROXY_URL", "http://claude-proxy:8319")

    if oauth_key:
        client = anthropic.Anthropic(base_url=proxy_url, api_key="oauth-proxy")
    else:
        client = anthropic.Anthropic(api_key=api_key)

    agent_name = agent_cfg.get("name", agent_cfg["id"])
    agent_role = agent_cfg.get("role", "assistant")

    # Load agent's identity files if available (for replaced agents too)
    project_root = Path(os.getenv("PROJECT_ROOT", "/app"))

    prompt_parts = []
    agents_dir = project_root / "agents" / agent_id
    for filename, label in [("SOUL.md", "Identity"), ("RULES.md", "Rules"), ("prompt.md", "Specialist Prompt")]:
        filepath = agents_dir / filename
        if filepath.exists():
            prompt_parts.append(f"# {label}\n\n{filepath.read_text(encoding='utf-8')}")

    if prompt_parts:
        system_prompt = "\n\n---\n\n".join(prompt_parts) + task_context
    else:
        system_prompt = (
            f"You are {agent_name} ({agent_role}). "
            "Be concise and focus on your speciality."
            + task_context
        )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=history,
    )
    reply = response.content[0].text

    # ── Persist both turns ───────────────────────────────────────────
    await db.executemany(
        """
        INSERT INTO chat_messages (agent_id, role, content, created_at)
        VALUES ($1, $2, $3, $4)
        """,
        [
            (agent_id, "user", body.message, now),
            (agent_id, "assistant", reply, now),
        ],
    )

    # ── Publish event ────────────────────────────────────────────────
    event = json.dumps(
        {
            "type": "chat_message",
            "agent_id": agent_id,
            "role": "assistant",
            "preview": reply[:120],
            "timestamp": now.isoformat(),
        }
    )
    await redis.publish("agent:events", event)

    return {"agent_id": agent_id, "reply": reply}
