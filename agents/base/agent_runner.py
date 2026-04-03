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
SOUL_PATH = Path("/app/shared/SOUL.md")
RULES_PATH = Path("/app/shared/RULES.md")
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

    soul = load_text_file(SOUL_PATH, "SOUL.md")
    if soul:
        parts.append(f"# SHARED IDENTITY (SOUL.md)\n\n{soul}")

    rules = load_text_file(RULES_PATH, "RULES.md")
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


# ── Redis Helpers ─────────────────────────────────────────────────────────────

async def publish_event(r: aioredis.Redis, event: dict) -> None:
    await r.publish(EVENTS_CHANNEL, json.dumps(event))


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

    # Add search tool status to system prompt
    if search_available:
        system_prompt += "\n\n## Search Tool Status\nagent-search-tool is AVAILABLE. Use AgentReach for all web research."
    else:
        system_prompt += "\n\n## Search Tool Status\nagent-search-tool is NOT available. Describe what you would search for and note the limitation."

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
                # Load prior agent context
                prior_context = await load_company_context(r, company_url)

                # Build the full user message
                user_message = description
                if company_url:
                    user_message = f"TARGET_COMPANY_URL: {company_url}\n\n{description}"
                if prior_context:
                    user_message += prior_context

                # If search tool is available, include it in context
                if search_available and company_url:
                    user_message += f"\n\n[Search tool ready. Use AgentReach().fetch('{company_url}') to start.]"

                # Call LLM with full context
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                output = response.content[0].text
                logger.info("Task %s completed (%d chars)", task_id, len(output))

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
