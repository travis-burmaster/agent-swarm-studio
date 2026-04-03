"""Chat router — direct conversations with individual agents."""

import json
import os
from datetime import datetime, timezone
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
    if not agent_cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    db = request.app.state.db
    redis = request.app.state.redis
    now = datetime.now(timezone.utc)

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

    # ── Call Anthropic ───────────────────────────────────────────────
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = (
        f"You are {agent_cfg['role']}. Goal: {agent_cfg['goal']}. "
        "Be concise and focus on your speciality."
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
