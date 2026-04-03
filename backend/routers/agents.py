"""Agents router — exposes agent list and per-agent status."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _agent_status_key(agent_id: str) -> str:
    return f"agent:status:{agent_id}"


async def _build_agent_info(request: Request, agent_cfg: dict) -> dict:
    agent_id = agent_cfg["id"]
    redis = request.app.state.redis

    raw: dict = await redis.hgetall(_agent_status_key(agent_id))

    return {
        "id": agent_id,
        "role": agent_cfg.get("role", ""),
        "goal": agent_cfg.get("goal", ""),
        "model": agent_cfg.get("model", ""),
        "color": agent_cfg.get("color", "#6366f1"),
        "tools": agent_cfg.get("tools", []),
        "status": raw.get("status", "offline"),
        "current_task": raw.get("current_task") or None,
        "last_output": raw.get("last_output") or None,
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_agents(request: Request):
    """Return all agents from config, enriched with live Redis status."""
    config = request.app.state.agents_config
    agents = config.get("agents", [])
    return [await _build_agent_info(request, a) for a in agents]


@router.get("/{agent_id}/status", response_model=Dict[str, Any])
async def get_agent_status(agent_id: str, request: Request):
    """Return status for a single agent."""
    config = request.app.state.agents_config
    agents = config.get("agents", [])
    agent_cfg = next((a for a in agents if a["id"] == agent_id), None)
    if not agent_cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return await _build_agent_info(request, agent_cfg)
