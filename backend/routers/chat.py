"""Chat router — direct conversations with individual agents."""

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import anthropic
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── Same search tools as agent_runner ────────────────────────────────────────

AGENT_TOOLS = [
    {
        "name": "web_fetch",
        "description": (
            "Fetch and read the content of any web page. Uses Jina Reader to extract "
            "clean text from URLs. Use this to read company websites, articles, legal pages, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (e.g. https://example.com/about)",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for information. Returns search results with titles, URLs, "
            "and snippets. Use this for research, finding company info, news, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a note to your persistent memory. Use this to remember important findings, "
            "key facts, or insights for future tasks and conversations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to remember",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall_memory",
        "description": (
            "Search your persistent memory for previously saved notes and findings. "
            "Returns your most recent memories matching the query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search term to filter memories. Leave empty for all recent memories.",
                    "default": "",
                },
            },
        },
    },
]


async def execute_tool(tool_name: str, tool_input: dict, agent_id: str, db) -> str:
    """Execute a tool and return the result as text."""
    try:
        if tool_name == "web_fetch":
            url = tool_input.get("url", "")
            if not url:
                return "Error: No URL provided"
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "30", f"https://r.jina.ai/{url}"],
                capture_output=True, text=True, timeout=35,
            )
            output = result.stdout.strip()
            return output[:15000] if output else f"Error: No content returned from {url}"
        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            if not query:
                return "Error: No query provided"
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "30", f"https://s.jina.ai/{query}"],
                capture_output=True, text=True, timeout=35,
            )
            output = result.stdout.strip()
            return output[:15000] if output else f"Error: No results for query: {query}"
        elif tool_name == "save_memory":
            content = tool_input.get("content", "")
            if not content:
                return "Error: No content provided"
            from datetime import datetime, timezone
            await db.execute(
                "INSERT INTO memory (agent_id, role, content, created_at) VALUES ($1, $2, $3, $4)",
                agent_id, "memory", content, datetime.now(timezone.utc),
            )
            logger.info("Chat agent %s saved memory (%d chars)", agent_id, len(content))
            return f"Memory saved successfully ({len(content)} chars)"
        elif tool_name == "recall_memory":
            query = tool_input.get("query", "")
            if query:
                rows = await db.fetch(
                    "SELECT content, created_at FROM memory WHERE agent_id = $1 AND content ILIKE $2 ORDER BY created_at DESC LIMIT 20",
                    agent_id, f"%{query}%",
                )
            else:
                rows = await db.fetch(
                    "SELECT content, created_at FROM memory WHERE agent_id = $1 ORDER BY created_at DESC LIMIT 20",
                    agent_id,
                )
            if not rows:
                return "No memories found." + (f" (searched for: {query})" if query else "")
            parts = []
            for row in reversed(rows):
                ts = row["created_at"].strftime("%Y-%m-%d %H:%M UTC") if row["created_at"] else ""
                parts.append(f"[{ts}] {row['content']}")
            return f"Found {len(rows)} memories:\n\n" + "\n\n---\n\n".join(parts)
        else:
            return f"Error: Unknown tool '{tool_name}'"
    except subprocess.TimeoutExpired:
        return f"Error: Tool '{tool_name}' timed out"
    except Exception as exc:
        return f"Error executing tool '{tool_name}': {exc}"

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

    # Load shared identity files first (SOUL, RULES, AGENTS, INSTRUCTIONS)
    for filename, label in [
        ("SOUL.md", "SHARED IDENTITY (SOUL.md)"),
        ("RULES.md", "OPERATING RULES (RULES.md)"),
        ("AGENTS.md", "TEAM PROTOCOL (AGENTS.md)"),
        ("INSTRUCTIONS.md", "EXECUTION INSTRUCTIONS (INSTRUCTIONS.md)"),
    ]:
        # Check multiple locations: project root, shared dir
        for search_dir in [project_root, project_root / "shared"]:
            filepath = search_dir / filename
            if filepath.exists():
                prompt_parts.append(f"# {label}\n\n{filepath.read_text(encoding='utf-8')}")
                break

    # Load agent-specific files
    agents_dir = project_root / "agents" / agent_id
    for filename, label in [("SOUL.md", "Agent Identity"), ("RULES.md", "Agent Rules"), ("prompt.md", "Specialist Prompt")]:
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

    # Add tool instructions and the same quality loop used by background agents
    system_prompt += (
        "\n\n## Available Tools\n"
        "You have access to these tools:\n"
        "- `web_fetch` — read any URL (company sites, legal pages, articles, etc.)\n"
        "- `web_search` — search the web for information\n"
        "- `save_memory` — save important findings to your persistent memory\n"
        "- `recall_memory` — search your memory for previously saved findings\n\n"
        "Use these tools when you need to look up real information or recall prior knowledge.\n"
        "Use recall_memory at the start of substantive tasks to check what you already know.\n\n"
        "## Task Execution Protocol\n"
        "For substantive tasks, follow this loop:\n"
        "1. Recall — start with recall_memory for relevant prior findings.\n"
        "2. Plan — make a short internal plan for what you need to verify.\n"
        "3. Gather — use web_search/web_fetch in sequence to collect evidence when facts matter.\n"
        "4. Verify — cross-check important claims against the fetched material.\n"
        "5. Self-critique — before finalizing, look for missing evidence, weak claims, or contradictions.\n"
        "6. Finalize — return a concise, well-structured answer with clear uncertainty where needed.\n"
        "Do not skip the self-critique step, and do not present unverified claims as facts."
    )

    # Tool-use agentic loop — up to 5 tool rounds for chat
    messages = history
    MAX_CHAT_TOOL_ROUNDS = 5
    tool_loop_exhausted = False
    for _turn in range(MAX_CHAT_TOOL_ROUNDS):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=AGENT_TOOLS,
        )

        if response.stop_reason != "tool_use":
            break

        # Process tool calls
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                logger.info("Chat %s — tool call: %s(%s)", agent_id, block.name, json.dumps(block.input)[:120])
                result_text = await execute_tool(block.name, block.input, agent_id, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })
        messages.append({"role": "user", "content": tool_results})
    else:
        tool_loop_exhausted = True

    # If loop ended while still doing tool_use, force a final text response
    # without re-running the last tool round.
    if tool_loop_exhausted:
        messages.append({"role": "user", "content": [{
            "type": "text",
            "text": "Provide your response now based on all the information gathered. Do not call any more tools.",
        }]})
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )

    # Extract final text reply
    reply = ""
    for block in response.content:
        if hasattr(block, "text"):
            reply += block.text

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
