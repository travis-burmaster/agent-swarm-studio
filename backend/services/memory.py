"""Postgres-backed long-term memory helpers."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import asyncpg


async def store_memory(
    pool: asyncpg.Pool,
    agent_id: str,
    role: str,
    content: str,
    session_id: Optional[str] = None,
) -> None:
    """
    Persist a memory entry for an agent.

    Args:
        pool:       asyncpg connection pool
        agent_id:   identifier of the agent
        role:       'user' | 'assistant' | 'system' | custom label
        content:    text content of the memory
        session_id: optional grouping key for a conversation session
    """
    await pool.execute(
        """
        INSERT INTO memory (agent_id, role, content, session_id, created_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        agent_id,
        role,
        content,
        session_id,
        datetime.now(timezone.utc),
    )


async def recall_memory(
    pool: asyncpg.Pool,
    agent_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent memory entries for an agent.

    Returns a list of dicts ordered chronologically (oldest first).
    """
    rows = await pool.fetch(
        """
        SELECT id, agent_id, role, content, session_id, created_at
        FROM memory
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        agent_id,
        limit,
    )
    # Return in chronological order
    return [dict(r) for r in reversed(rows)]
