"""Agents router — exposes agent list and per-agent status."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.registry_client import fetch_registry_agent
from services.agent_swap import (
    backup_agent,
    get_replacement_info,
    replace_agent_files,
    restart_agent_container,
    restore_agent,
    update_agent_yaml,
    validate_slot,
    write_manifest,
)

logger = logging.getLogger(__name__)


class ReplaceRequest(BaseModel):
    registry_url: str


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


@router.post("/{agent_id}/replace")
async def replace_agent_endpoint(agent_id: str, body: ReplaceRequest, request: Request):
    """Replace an agent slot with an agent from the gitagent registry."""
    try:
        validate_slot(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        # Fetch from registry
        registry_agent = await fetch_registry_agent(body.registry_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from registry: {e}")

    # Get current agent info for backup
    config = request.app.state.agents_config
    agent_cfg = next((a for a in config.get("agents", []) if a["id"] == agent_id), None)
    if not agent_cfg:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in config")

    original_name = agent_cfg.get("name", "")
    original_role = agent_cfg.get("role", "")

    # Backup current agent
    backup_agent(agent_id)
    write_manifest(agent_id, original_name, original_role, registry_agent)

    # Replace files + update config
    replace_agent_files(agent_id, registry_agent)
    update_agent_yaml(agent_id, registry_agent)

    # Update in-memory config to reflect the change
    for a in config.get("agents", []):
        if a["id"] == agent_id:
            a["name"] = registry_agent.display_name
            a["role"] = registry_agent.role
            if registry_agent.capabilities:
                a["capabilities"] = registry_agent.capabilities
            if registry_agent.tags:
                a["tags"] = registry_agent.tags
            break

    # Restart container
    try:
        restart_agent_container(agent_id)
    except Exception as e:
        logger.warning("Container restart failed (may need manual restart): %s", e)

    return {
        "agent_id": agent_id,
        "new_name": registry_agent.display_name,
        "new_role": registry_agent.role,
        "registry_url": registry_agent.source_url,
        "backup_exists": True,
        "status": "restarting",
    }


@router.post("/{agent_id}/restore")
async def restore_agent_endpoint(agent_id: str, request: Request):
    """Restore the original agent from backup."""
    try:
        validate_slot(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        manifest = restore_agent(agent_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Update in-memory config
    config = request.app.state.agents_config
    for a in config.get("agents", []):
        if a["id"] == agent_id:
            a["name"] = manifest["original_name"]
            a["role"] = manifest["original_role"]
            break

    # Restart container
    try:
        restart_agent_container(agent_id)
    except Exception as e:
        logger.warning("Container restart failed (may need manual restart): %s", e)

    return {
        "agent_id": agent_id,
        "restored_name": manifest["original_name"],
        "restored_role": manifest["original_role"],
        "status": "restarting",
    }


@router.get("/{agent_id}/replacement-info")
async def get_replacement_info_endpoint(agent_id: str):
    """Check if an agent slot has been replaced and get metadata."""
    try:
        return get_replacement_info(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
