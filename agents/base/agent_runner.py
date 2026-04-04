"""
Agent Runner — generic worker loop for all Agent Swarm Studio agents.

Environment variables:
  AGENT_ID          — unique agent identifier (e.g. "coder")
  REDIS_URL         — Redis connection string
  DATABASE_URL      — Postgres DSN
  ANTHROPIC_API_KEY — Anthropic API key
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
PROMPT_PATH = Path("/app/prompt.md")
TASK_QUEUE_KEY = f"tasks:{AGENT_ID}"
STATUS_KEY = f"agent:status:{AGENT_ID}"
EVENTS_CHANNEL = "agent:events"


# ── Helpers ────────────────────────────────────────────────────────────────────

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


# ── Main loop ──────────────────────────────────────────────────────────────────

async def main() -> None:
    # Load system prompt — AGENTS.md rules first, then role-specific prompt
    prompt_parts = []
    for rules_path in [Path("/app/AGENTS.md"), Path("/shared/workspace/AGENTS.md")]:
        if rules_path.exists():
            prompt_parts.append(f"# Swarm Rules\n{rules_path.read_text()}")
            logger.info("Loaded swarm rules from %s", rules_path)
            break
    if PROMPT_PATH.exists():
        prompt_parts.append(f"# Your Role\n{PROMPT_PATH.read_text()}")
        logger.info("Loaded role prompt from %s", PROMPT_PATH)
    else:
        prompt_parts.append(f"You are a helpful AI agent with ID '{AGENT_ID}'.")
        logger.warning("No prompt.md found, using default system prompt.")
    system_prompt = "\n\n---\n\n".join(prompt_parts)

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

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # ── Event loop ─────────────────────────────────────────────────────────────
    while True:
        try:
            result = await r.brpop(TASK_QUEUE_KEY, timeout=5)
            if result is None:
                # Timeout — stay idle, loop again
                continue

            _key, raw = result
            task = json.loads(raw)
            task_id = task.get("task_id", "unknown")
            description = task.get("description", "")

            logger.info("Received task %s: %s", task_id, description[:80])

            # Mark working
            await update_status(r, "working", current_task=description[:120])
            await publish_event(
                r,
                {
                    "type": "task_started",
                    "agent_id": AGENT_ID,
                    "task_id": task_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            await update_task(pool, task_id, "in_progress", "")

            try:
                # Call LLM
                response = client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": description}],
                )
                output = response.content[0].text
                logger.info("Task %s completed (%d chars)", task_id, len(output))

                # Persist result
                await update_task(pool, task_id, "completed", output)
                await store_memory(pool, "assistant", f"Task: {description}\n\nResult: {output}")

                # Publish completion
                await publish_event(
                    r,
                    {
                        "type": "task_completed",
                        "agent_id": AGENT_ID,
                        "task_id": task_id,
                        "result_preview": output[:200],
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
