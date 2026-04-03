"""Agent status management helpers."""

import json
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis


async def update_agent_status(
    redis: aioredis.Redis,
    agent_id: str,
    status: str,
    current_task: Optional[str] = None,
    last_output: Optional[str] = None,
) -> None:
    """
    Update agent runtime state in Redis and publish a status event.

    Stores fields in hash  agent:status:{agent_id}
    Publishes JSON event to  agent:events  channel.
    """
    key = f"agent:status:{agent_id}"

    mapping: dict = {"status": status}
    if current_task is not None:
        mapping["current_task"] = current_task
    if last_output is not None:
        mapping["last_output"] = last_output[:500]  # trim for Redis

    await redis.hset(key, mapping=mapping)

    event = json.dumps(
        {
            "type": "agent_status",
            "agent_id": agent_id,
            "status": status,
            "current_task": current_task,
            "last_output": last_output[:120] if last_output else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    await redis.publish("agent:events", event)
