"""Tasks router — create, list, and delete tasks."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class TaskCreate(BaseModel):
    description: str
    assign_to: str = "orchestrator"


@router.post("", response_model=Dict[str, Any], status_code=201)
async def create_task(body: TaskCreate, request: Request):
    """Create a new task, enqueue it in Redis, and persist to Postgres."""
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    db = request.app.state.db
    redis = request.app.state.redis

    # Persist to Postgres
    await db.execute(
        """
        INSERT INTO tasks (id, description, assign_to, status, created_at, updated_at)
        VALUES ($1, $2, $3, 'pending', $4, $4)
        """,
        task_id,
        body.description,
        body.assign_to,
        now,
    )

    # Push to Redis task queue for the assigned agent
    task_payload = json.dumps(
        {"task_id": task_id, "description": body.description, "assign_to": body.assign_to}
    )
    await redis.lpush(f"tasks:{body.assign_to}", task_payload)

    # Publish event
    event = json.dumps(
        {
            "type": "task_created",
            "task_id": task_id,
            "description": body.description,
            "assign_to": body.assign_to,
            "timestamp": now.isoformat(),
        }
    )
    await redis.publish("agent:events", event)

    return {
        "id": task_id,
        "description": body.description,
        "assign_to": body.assign_to,
        "status": "pending",
        "created_at": now.isoformat(),
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_tasks(request: Request):
    """Fetch last 50 tasks ordered by creation date descending."""
    db = request.app.state.db
    rows = await db.fetch(
        """
        SELECT id::text, description, assign_to, status, result,
               created_at, updated_at
        FROM tasks
        ORDER BY created_at DESC
        LIMIT 50
        """
    )
    return [dict(r) for r in rows]


@router.delete("", response_model=Dict[str, Any])
async def clear_all_tasks(request: Request):
    """Clear all task history, memory, and agent queues without restarting."""
    db = request.app.state.db
    redis = request.app.state.redis

    # Truncate tables
    await db.execute("TRUNCATE TABLE tasks CASCADE")
    for table in ("memory", "chat_messages"):
        try:
            await db.execute(f"TRUNCATE TABLE {table} CASCADE")
        except Exception:
            pass  # table may not exist in all deployments

    # Flush all agent Redis queues and reset statuses
    agent_ids: List[str] = []
    try:
        rows = await db.fetch("SELECT id FROM agents")
        agent_ids = [r["id"] for r in rows]
    except Exception:
        agent_ids = ["orchestrator", "coder", "reviewer", "tester",
                     "lawyer", "data-researcher", "marketing", "sales"]

    for agent_id in agent_ids:
        await redis.delete(f"tasks:{agent_id}")
        await redis.hset("agent:status", agent_id, "idle")

    # Broadcast event to UI via WebSocket
    event = json.dumps({"type": "history_cleared", "timestamp": datetime.now(timezone.utc).isoformat()})
    await redis.publish("agent:events", event)

    return {"cleared": True, "tables": ["tasks", "memory", "chat_messages"], "queues_flushed": agent_ids}


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request):
    """Delete a task by ID."""
    db = request.app.state.db
    result = await db.execute("DELETE FROM tasks WHERE id = $1", task_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
