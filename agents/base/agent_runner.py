"""
Agent Runner — Business Intelligence Swarm
Agent Swarm Studio v2.0.0

Loads shared identity files (SOUL.md, RULES.md, AGENTS.md, INSTRUCTIONS.md),
initializes agent-search-tool, and processes tasks from Redis queue.

LLM access (pick one):
  Option A: ANTHROPIC_API_KEY       — direct Anthropic API access
  Option B: ANTHROPIC_OAUTH_KEY     — routes through Claude OAuth Proxy (CLAUDE_PROXY_URL)

Environment variables:
  AGENT_ID              — unique agent identifier (lawyer, data-researcher, marketing, sales)
  REDIS_URL             — Redis connection string
  DATABASE_URL          — Postgres DSN
  ANTHROPIC_API_KEY     — Anthropic API key (direct access)
  ANTHROPIC_OAUTH_KEY   — OAuth token (uses proxy)
  CLAUDE_PROXY_URL      — URL of the Claude OAuth Proxy service
  TARGET_COMPANY_URL    — shared company URL context for all agents (set per workflow)
  AGENT_SEARCH_CONFIG   — optional path to agent-search config dir
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import asyncpg
import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

AGENT_ID = os.environ["AGENT_ID"]
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agentuser:agentpass@postgres:5432/agents")

# Paths inside the container
PROMPT_PATH = Path("/app/prompt.md")
# Agent-local SOUL/RULES take priority over shared (for registry replacements)
SOUL_PATH_LOCAL = Path("/app/SOUL.md")
SOUL_PATH_SHARED = Path("/app/shared/SOUL.md")
RULES_PATH_LOCAL = Path("/app/RULES.md")
RULES_PATH_SHARED = Path("/app/shared/RULES.md")
AGENTS_PATH = Path("/app/shared/AGENTS.md")
INSTRUCTIONS_PATH = Path("/app/shared/INSTRUCTIONS.md")

TASK_QUEUE_KEY = f"tasks:{AGENT_ID}"
STATUS_KEY = f"agent:status:{AGENT_ID}"
EVENTS_CHANNEL = "agent:events"
COMPANY_CONTEXT_PREFIX = "company:context:"


# ── File Loading ───────────────────────────────────────────────────────────────

def load_text_file(path: Path, label: str) -> str:
    """Load a text file, returning empty string with a warning if not found."""
    if path.exists():
        content = path.read_text(encoding="utf-8")
        logger.info("Loaded %s from %s (%d chars)", label, path, len(content))
        return content
    else:
        logger.warning("%s not found at %s — skipping", label, path)
        return ""


def build_system_prompt() -> str:
    """
    Assemble the full system prompt from shared identity files + agent-specific prompt.
    Order: SOUL → RULES → AGENTS → INSTRUCTIONS → agent prompt
    """
    parts = []

    # Prefer agent-local SOUL.md/RULES.md (from registry replacement), fall back to shared
    soul_path = SOUL_PATH_LOCAL if SOUL_PATH_LOCAL.exists() else SOUL_PATH_SHARED
    soul = load_text_file(soul_path, "SOUL.md")
    if soul:
        parts.append(f"# SHARED IDENTITY (SOUL.md)\n\n{soul}")

    rules_path = RULES_PATH_LOCAL if RULES_PATH_LOCAL.exists() else RULES_PATH_SHARED
    rules = load_text_file(rules_path, "RULES.md")
    if rules:
        parts.append(f"# OPERATING RULES (RULES.md)\n\n{rules}")

    agents_doc = load_text_file(AGENTS_PATH, "AGENTS.md")
    if agents_doc:
        parts.append(f"# TEAM PROTOCOL (AGENTS.md)\n\n{agents_doc}")

    instructions = load_text_file(INSTRUCTIONS_PATH, "INSTRUCTIONS.md")
    if instructions:
        parts.append(f"# EXECUTION INSTRUCTIONS (INSTRUCTIONS.md)\n\n{instructions}")

    agent_prompt = load_text_file(PROMPT_PATH, f"{AGENT_ID}/prompt.md")
    if agent_prompt:
        parts.append(f"# YOUR SPECIALIST ROLE\n\n{agent_prompt}")
    else:
        parts.append(f"You are a helpful AI agent with ID '{AGENT_ID}' in the Business Intelligence Swarm.")

    return "\n\n---\n\n".join(parts)


# ── Search Tool Initialization ────────────────────────────────────────────────

def init_search_tool():
    """
    Initialize agent-search-tool (AgentReach).
    Returns the AgentReach instance or None if not available.
    """
    try:
        from agent_search import AgentReach  # type: ignore
        reach = AgentReach()
        logger.info("agent-search-tool initialized for agent %s", AGENT_ID)
        return reach
    except ImportError:
        logger.warning(
            "agent-search-tool not installed. Web search capabilities unavailable. "
            "Install with: pip install agent-search-tool"
        )
        return None
    except Exception as exc:
        logger.warning("agent-search-tool init failed: %s", exc)
        return None


# ── Claude Tool Definitions ──────────────────────────────────────────────────

AGENT_TOOLS = [
    {
        "name": "web_fetch",
        "description": (
            "Fetch and read the content of any web page. Uses Jina Reader to extract "
            "clean text from URLs. Use this to read company websites, articles, legal pages, "
            "privacy policies, terms of service, LinkedIn profiles, etc."
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
            "and snippets. Use this to find company information, news, legal filings, "
            "market data, competitor analysis, reviews, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. '\"Acme Corp\" revenue funding')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a note to your persistent memory. Use this to remember important findings, "
            "key facts, insights, or anything you want to recall in future tasks. "
            "Memories persist across tasks and conversations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to remember (key findings, facts, insights, analysis notes)",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall_memory",
        "description": (
            "Search your persistent memory for previously saved notes and findings. "
            "Use this to recall what you've learned in prior tasks — key facts, insights, "
            "company profiles, analysis results, etc. Returns your most recent memories "
            "matching the query, or all recent memories if no query is provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search term to filter memories (e.g. company name, topic). Leave empty to get all recent memories.",
                    "default": "",
                },
            },
        },
    },
]


async def execute_tool(tool_name: str, tool_input: dict, pool: asyncpg.Pool = None) -> str:
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
            if not output:
                return f"Error: No content returned from {url}"
            return output[:15000]

        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            if not query:
                return "Error: No query provided"
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "30", f"https://s.jina.ai/{query}"],
                capture_output=True, text=True, timeout=35,
            )
            output = result.stdout.strip()
            if not output:
                return f"Error: No results for query: {query}"
            return output[:15000]

        elif tool_name == "save_memory":
            content = tool_input.get("content", "")
            if not content:
                return "Error: No content provided"
            if pool:
                await pool.execute(
                    "INSERT INTO memory (agent_id, role, content, created_at) VALUES ($1, $2, $3, $4)",
                    AGENT_ID, "memory", content, datetime.now(timezone.utc),
                )
                logger.info("Agent %s saved memory (%d chars)", AGENT_ID, len(content))
                return f"Memory saved successfully ({len(content)} chars)"
            return "Error: Database not available"

        elif tool_name == "recall_memory":
            query = tool_input.get("query", "")
            if pool:
                if query:
                    rows = await pool.fetch(
                        """
                        SELECT content, created_at FROM memory
                        WHERE agent_id = $1 AND content ILIKE $2
                        ORDER BY created_at DESC LIMIT 20
                        """,
                        AGENT_ID, f"%{query}%",
                    )
                else:
                    rows = await pool.fetch(
                        """
                        SELECT content, created_at FROM memory
                        WHERE agent_id = $1
                        ORDER BY created_at DESC LIMIT 20
                        """,
                        AGENT_ID,
                    )
                if not rows:
                    return "No memories found." + (f" (searched for: {query})" if query else "")
                parts = []
                for row in reversed(rows):
                    ts = row["created_at"].strftime("%Y-%m-%d %H:%M UTC") if row["created_at"] else ""
                    parts.append(f"[{ts}] {row['content']}")
                return f"Found {len(rows)} memories:\n\n" + "\n\n---\n\n".join(parts)
            return "Error: Database not available"

        else:
            return f"Error: Unknown tool '{tool_name}'"
    except subprocess.TimeoutExpired:
        return f"Error: Tool '{tool_name}' timed out after 30 seconds"
    except Exception as exc:
        return f"Error executing tool '{tool_name}': {exc}"


# ── Redis Helpers ─────────────────────────────────────────────────────────────

async def publish_event(r: aioredis.Redis, event: dict) -> None:
    await r.publish(EVENTS_CHANNEL, json.dumps(event))


async def publish_task_phase(
    r: aioredis.Redis,
    task_id: str,
    phase: str,
    detail: str = "",
) -> None:
    await publish_event(
        r,
        {
            "type": "task_phase",
            "agent_id": AGENT_ID,
            "task_id": task_id,
            "phase": phase,
            "detail": detail[:180] or None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def update_status(
    r: aioredis.Redis,
    status: str,
    current_task: str = "",
    last_output: str = "",
) -> None:
    await r.hset(
        STATUS_KEY,
        mapping={
            "status": status,
            "current_task": current_task,
            "last_output": last_output[:500],
        },
    )
    await publish_event(
        r,
        {
            "type": "agent_status",
            "agent_id": AGENT_ID,
            "status": status,
            "current_task": current_task or None,
            "last_output": last_output[:120] or None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ── Postgres Helpers ──────────────────────────────────────────────────────────

async def store_memory(pool: asyncpg.Pool, role: str, content: str) -> None:
    await pool.execute(
        "INSERT INTO memory (agent_id, role, content, created_at) VALUES ($1, $2, $3, $4)",
        AGENT_ID,
        role,
        content,
        datetime.now(timezone.utc),
    )


async def update_task(pool: asyncpg.Pool, task_id: str, status: str, result: str) -> None:
    await pool.execute(
        "UPDATE tasks SET status=$1, result=$2, updated_at=$3 WHERE id=$4",
        status,
        result,
        datetime.now(timezone.utc),
        task_id,
    )


# ── Context Loading ───────────────────────────────────────────────────────────

async def load_all_task_history(pool: asyncpg.Pool, limit: int = 10) -> str:
    """
    Load recent completed task results from ALL agents in the swarm.
    Each agent sees what every other agent has done — enabling cross-agent
    awareness and building on prior findings across the full swarm.
    """
    rows = await pool.fetch(
        """
        SELECT assign_to, description, result, updated_at FROM tasks
        WHERE status = 'completed' AND result IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT $1
        """,
        limit,
    )
    if not rows:
        return ""

    own_parts = []
    other_parts = []
    for row in reversed(rows):
        ts = row["updated_at"].strftime("%Y-%m-%d %H:%M UTC") if row["updated_at"] else ""
        agent = row["assign_to"]
        entry = (
            f"### [{agent}] Task: {row['description']}\n"
            f"Completed: {ts}\n"
            f"{row['result'][:3000]}"
        )
        if agent == AGENT_ID:
            own_parts.append(entry)
        else:
            other_parts.append(entry)

    sections = []
    if own_parts:
        sections.append(
            "## Your Prior Task Results\n\n" + "\n\n---\n\n".join(own_parts)
        )
    if other_parts:
        sections.append(
            "## Other Agents' Task Results (cross-agent context)\n\n"
            + "\n\n---\n\n".join(other_parts)
        )
    return "\n\n" + "\n\n".join(sections) if sections else ""


async def load_company_context(r: aioredis.Redis, company_url: str) -> str:
    """
    Load prior agent findings for this company from Redis cache.
    Returns a formatted context string to prepend to the task.
    """
    if not company_url:
        return ""

    url_slug = company_url.replace("https://", "").replace("http://", "").replace("/", "_").rstrip("_")
    context_parts = []

    # Load outputs from other agents
    for other_agent in ["data-researcher", "lawyer", "marketing", "sales"]:
        if other_agent == AGENT_ID:
            continue
        cache_key = f"agent:output:{other_agent}:{url_slug}"
        cached = await r.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                output = data.get("output", "")
                if output:
                    context_parts.append(
                        f"### Prior analysis from {other_agent}:\n{output[:3000]}"
                    )
                    logger.info("Loaded prior context from %s for %s", other_agent, company_url)
            except json.JSONDecodeError:
                pass

    if context_parts:
        return "\n\n## Prior Agent Findings (use as context):\n\n" + "\n\n".join(context_parts)
    return ""


async def cache_agent_output(r: aioredis.Redis, company_url: str, output: str) -> None:
    """Cache this agent's output for other agents to reference."""
    if not company_url:
        return
    url_slug = company_url.replace("https://", "").replace("http://", "").replace("/", "_").rstrip("_")
    cache_key = f"agent:output:{AGENT_ID}:{url_slug}"
    await r.set(
        cache_key,
        json.dumps({
            "output": output,
            "agent_id": AGENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        ex=86400  # 24-hour TTL
    )
    logger.info("Cached output for %s at %s", AGENT_ID, cache_key)


# ── Main Loop ─────────────────────────────────────────────────────────────────

async def main() -> None:
    # Build the full system prompt from shared files + agent prompt
    system_prompt = build_system_prompt()
    logger.info("System prompt built: %d chars", len(system_prompt))

    # Initialize search tool
    reach = init_search_tool()
    search_available = reach is not None

    # Add tool instructions to system prompt
    system_prompt += (
        "\n\n## Available Tools\n"
        "You have access to these tools:\n"
        "- `web_fetch` — read any URL (company sites, legal pages, articles, etc.)\n"
        "- `web_search` — search the web for information\n"
        "- `save_memory` — save important findings to your persistent memory for future tasks\n"
        "- `recall_memory` — search your memory for previously saved findings and insights\n\n"
        "ALWAYS use web_fetch/web_search to gather real data. Do NOT fabricate information.\n"
        "Use recall_memory at the START of a task to check what you already know.\n"
        "Use save_memory to store key findings, insights, and facts you want to remember.\n\n"
        "## Task Execution Protocol\n"
        "For every task, follow this loop:\n"
        "1. Recall — start with recall_memory for relevant prior findings.\n"
        "2. Plan — make a short internal plan for what you need to verify.\n"
        "3. Gather — use web_search/web_fetch in sequence to collect evidence.\n"
        "4. Verify — cross-check important claims against the fetched material.\n"
        "5. Self-critique — before finalizing, look for missing evidence, weak claims, or contradictions.\n"
        "6. Finalize — return a concise, well-structured report with clear uncertainty where needed.\n"
        "Do not skip the self-critique step, and do not present unverified claims as facts."
    )

    # Connect to Redis
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await r.ping()
    logger.info("Connected to Redis at %s", REDIS_URL)

    # Connect to Postgres
    pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=5)
    logger.info("Connected to Postgres at %s", DATABASE_URL)

    # Announce idle
    await update_status(r, "idle")
    logger.info("Agent %s ready — listening on queue '%s'", AGENT_ID, TASK_QUEUE_KEY)

    # Initialize LLM client — proxy mode (OAuth) or direct API key
    oauth_key = os.getenv("ANTHROPIC_OAUTH_KEY", "").strip()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    proxy_url = os.getenv("CLAUDE_PROXY_URL", "http://claude-proxy:8319")

    if oauth_key:
        # Route through Claude OAuth Proxy — proxy handles auth headers
        logger.info("Using Claude OAuth Proxy at %s", proxy_url)
        client = anthropic.Anthropic(
            base_url=proxy_url,
            api_key="oauth-proxy",  # placeholder — proxy injects real auth
        )
    elif api_key:
        logger.info("Using direct Anthropic API key")
        client = anthropic.Anthropic(api_key=api_key)
    else:
        raise RuntimeError(
            "No LLM credentials configured. Set ANTHROPIC_API_KEY or ANTHROPIC_OAUTH_KEY in .env"
        )

    # ── Event loop ─────────────────────────────────────────────────────────────
    while True:
        try:
            result = await r.brpop(TASK_QUEUE_KEY, timeout=5)
            if result is None:
                continue

            _key, raw = result
            task = json.loads(raw)
            task_id = task.get("task_id", "unknown")
            description = task.get("description", "")

            # ── Atomic task checkout (Paperclip pattern) ──────────────────────
            # Acquire an exclusive lock before processing. Prevents duplicate
            # execution if the same task_id is retried or re-queued on error,
            # and is safe for future horizontal scaling (multiple containers
            # per agent type). Lock expires after 10 minutes as a safety net.
            lock_key = f"task:lock:{task_id}"
            acquired = await r.set(lock_key, AGENT_ID, nx=True, ex=600)
            if not acquired:
                logger.warning(
                    "Task %s already locked by another worker — skipping", task_id
                )
                continue
            # ─────────────────────────────────────────────────────────────────

            # Extract company URL context
            task_context = task.get("context", {})
            company_url = (
                task_context.get("company_url")
                or os.getenv("TARGET_COMPANY_URL", "")
            )

            logger.info("Received task %s: %s", task_id, description[:80])
            if company_url:
                logger.info("Target company URL: %s", company_url)

            # Mark working
            await update_status(r, "working", current_task=description[:120])
            await publish_event(
                r,
                {
                    "type": "task_started",
                    "agent_id": AGENT_ID,
                    "task_id": task_id,
                    "company_url": company_url,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await update_task(pool, task_id, "in_progress", "")

            try:
                await publish_task_phase(r, task_id, "recall", "Loading prior swarm task history")
                # Load task history from ALL agents in the swarm
                task_history = await load_all_task_history(pool)

                await publish_task_phase(r, task_id, "context", "Loading prior agent findings for this company")
                # Load prior agent context (other agents' findings)
                prior_context = await load_company_context(r, company_url)

                await publish_task_phase(r, task_id, "plan", "Building task prompt with workflow context")
                # Build the full user message
                user_message = description
                if company_url:
                    user_message = f"TARGET_COMPANY_URL: {company_url}\n\n{description}"
                if task_history:
                    user_message += task_history
                if prior_context:
                    user_message += prior_context

                # Call LLM with tools and handle tool-use loop
                messages = [{"role": "user", "content": user_message}]

                await publish_task_phase(r, task_id, "gather", "Running tool-assisted analysis loop")
                # Tool-use agentic loop — up to 8 rounds of tool calls
                MAX_TOOL_ROUNDS = 8
                tool_loop_exhausted = False
                for _turn in range(MAX_TOOL_ROUNDS):
                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=8192,
                        system=system_prompt,
                        messages=messages,
                        tools=AGENT_TOOLS,
                    )

                    # If no tool use, we're done
                    if response.stop_reason != "tool_use":
                        break

                    # Process tool calls
                    assistant_content = response.content
                    messages.append({"role": "assistant", "content": assistant_content})

                    tool_results = []
                    for block in assistant_content:
                        if block.type == "tool_use":
                            tool_input_preview = json.dumps(block.input)[:120]
                            logger.info(
                                "Task %s — tool call: %s(%s)",
                                task_id, block.name,
                                tool_input_preview,
                            )
                            await publish_event(
                                r,
                                {
                                    "type": "tool_called",
                                    "agent_id": AGENT_ID,
                                    "task_id": task_id,
                                    "tool_name": block.name,
                                    "tool_input_preview": tool_input_preview,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                            result_text = await execute_tool(block.name, block.input, pool)
                            await publish_event(
                                r,
                                {
                                    "type": "tool_result",
                                    "agent_id": AGENT_ID,
                                    "task_id": task_id,
                                    "tool_name": block.name,
                                    "result_preview": result_text[:180],
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text,
                            })
                    messages.append({"role": "user", "content": tool_results})
                else:
                    tool_loop_exhausted = True

                # If the loop ended while still doing tool_use, force a final
                # text response by calling without tools. Reuse the already
                # appended tool results instead of executing the last tool round twice.
                if tool_loop_exhausted:
                    logger.info("Task %s — tool loop exhausted, forcing final summary", task_id)
                    messages.append({"role": "user", "content": [{
                        "type": "text",
                        "text": "You have used all available tool calls. Now write your COMPLETE analysis report based on everything you have gathered. Do NOT call any more tools.",
                    }]})
                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=8192,
                        system=system_prompt,
                        messages=messages,
                    )

                await publish_task_phase(r, task_id, "self_critique", "Reviewing gathered evidence and producing final answer")
                # Extract final text output
                output = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        output += block.text
                logger.info("Task %s completed (%d chars)", task_id, len(output))

                await publish_task_phase(r, task_id, "finalize", "Persisting result and sharing cross-agent context")
                # Cache output for other agents
                if company_url:
                    await cache_agent_output(r, company_url, output)

                # Persist result
                await update_task(pool, task_id, "completed", output)
                await store_memory(
                    pool,
                    "assistant",
                    f"AGENT: {AGENT_ID}\nCOMPANY: {company_url}\nTASK: {description[:200]}\n\nRESULT:\n{output[:2000]}"
                )

                # Publish completion
                await publish_event(
                    r,
                    {
                        "type": "task_completed",
                        "agent_id": AGENT_ID,
                        "task_id": task_id,
                        "company_url": company_url,
                        "result_preview": output[:300],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await update_status(r, "idle", last_output=output[:200])

            except Exception as task_err:
                logger.error("Task %s failed: %s", task_id, task_err)
                error_msg = str(task_err)
                await update_task(pool, task_id, "failed", error_msg)
                await publish_event(
                    r,
                    {
                        "type": "task_error",
                        "agent_id": AGENT_ID,
                        "task_id": task_id,
                        "error": error_msg[:300],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await update_status(r, "idle", last_output=f"ERROR: {error_msg[:100]}")
            finally:
                current_lock_owner = await r.get(lock_key)
                if current_lock_owner == AGENT_ID:
                    await r.delete(lock_key)

        except asyncio.CancelledError:
            break
        except Exception as loop_err:
            logger.error("Runner loop error: %s", loop_err)
            await asyncio.sleep(2)

    # Cleanup
    await update_status(r, "offline")
    await r.aclose()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
