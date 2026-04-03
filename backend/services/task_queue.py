"""Redis-backed task queue helpers."""

import json
from typing import Any, Dict, Optional

import redis.asyncio as aioredis


async def push_task(redis: aioredis.Redis, agent_id: str, task_dict: Dict[str, Any]) -> None:
    """Push a task payload to the agent's Redis list (left push)."""
    await redis.lpush(f"tasks:{agent_id}", json.dumps(task_dict))


async def pop_task(
    redis: aioredis.Redis,
    agent_id: str,
    timeout: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Blocking right-pop from the agent's task queue.

    Returns the decoded task dict, or None on timeout.
    """
    result = await redis.brpop(f"tasks:{agent_id}", timeout=timeout)
    if result is None:
        return None
    _key, raw = result
    return json.loads(raw)


async def get_queue_length(redis: aioredis.Redis, agent_id: str) -> int:
    """Return the number of pending tasks for an agent."""
    return await redis.llen(f"tasks:{agent_id}")
