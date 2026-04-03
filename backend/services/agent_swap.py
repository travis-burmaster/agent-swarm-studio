"""Agent swap service — backup, replace, and restore agent slots."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from services.registry_client import RegistryAgent

# Resolve project root — in Docker the backend runs from /app/ and volumes
# mount the project files. Use PROJECT_ROOT env var if set, otherwise walk
# up from this file's location to find agent.yaml.
import os as _os

def _find_project_root() -> Path:
    """Find the project root by env var or by walking up to find agent.yaml."""
    env_root = _os.getenv("PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    # Walk up from this file looking for agent.yaml
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / "agent.yaml").exists():
        return candidate
    # In Docker, agent.yaml is mounted at /app/agent.yaml
    if Path("/app/agent.yaml").exists():
        return Path("/app")
    return candidate

PROJECT_ROOT = _find_project_root()


def _agents_dir(slot_id: str) -> Path:
    # In Docker: /app/agents/<slot> (volume-mounted from ./agents/<slot>)
    return PROJECT_ROOT / "agents" / slot_id


def _skills_dir(slot_id: str) -> Path:
    # In Docker: /app/.agents/skills/<slot> (volume-mounted from ./.agents/skills/<slot>)
    return PROJECT_ROOT / ".agents" / "skills" / slot_id


def _backup_dir(slot_id: str) -> Path:
    return _agents_dir(slot_id) / ".backup"


def _manifest_path(slot_id: str) -> Path:
    return _backup_dir(slot_id) / "manifest.json"


def _agent_yaml_path() -> Path:
    return PROJECT_ROOT / "agent.yaml"


VALID_SLOTS = {"lawyer", "data-researcher", "marketing", "sales"}


def validate_slot(slot_id: str) -> None:
    if slot_id not in VALID_SLOTS:
        raise ValueError(f"Unknown agent slot '{slot_id}'. Valid slots: {', '.join(sorted(VALID_SLOTS))}")


def get_replacement_info(slot_id: str) -> dict:
    """Return replacement status for an agent slot."""
    validate_slot(slot_id)
    manifest_path = _manifest_path(slot_id)
    if not manifest_path.exists():
        return {
            "agent_id": slot_id,
            "is_replaced": False,
            "registry_url": None,
            "replacement_name": None,
            "replaced_at": None,
            "backup_exists": False,
            "original_name": None,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replaced_by = manifest.get("replaced_by", {})
    return {
        "agent_id": slot_id,
        "is_replaced": True,
        "registry_url": replaced_by.get("registry_url"),
        "replacement_name": replaced_by.get("name"),
        "replaced_at": replaced_by.get("fetched_at"),
        "backup_exists": True,
        "original_name": manifest.get("original_name"),
    }


def backup_agent(slot_id: str) -> None:
    """Back up the current agent's prompt, identity files, and skills before replacement."""
    validate_slot(slot_id)
    backup = _backup_dir(slot_id)

    # Remove previous backup if it exists
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)

    agent_dir = _agents_dir(slot_id)

    # Back up prompt.md, SOUL.md, RULES.md
    for filename in ("prompt.md", "SOUL.md", "RULES.md"):
        src = agent_dir / filename
        if src.exists():
            shutil.copy2(src, backup / filename)

    # Back up skills
    skills_src = _skills_dir(slot_id)
    if skills_src.exists():
        shutil.copytree(skills_src, backup / "skills")


def write_manifest(slot_id: str, original_name: str, original_role: str, registry_agent: RegistryAgent) -> None:
    """Write the backup manifest with metadata about the replacement."""
    manifest = {
        "original_name": original_name,
        "original_role": original_role,
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "replaced_by": {
            "registry_url": registry_agent.source_url,
            "name": registry_agent.display_name,
            "owner": registry_agent.owner,
            "agent_name": registry_agent.name,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    _manifest_path(slot_id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def replace_agent_files(slot_id: str, registry_agent: RegistryAgent) -> None:
    """Write the registry agent's prompt, identity files, and skills to the agent slot."""
    validate_slot(slot_id)
    agent_dir = _agents_dir(slot_id)

    # Write new prompt.md
    (agent_dir / "prompt.md").write_text(registry_agent.prompt_content, encoding="utf-8")

    # Write SOUL.md and RULES.md if the registry agent provides them
    if registry_agent.soul_content:
        (agent_dir / "SOUL.md").write_text(registry_agent.soul_content, encoding="utf-8")
    if registry_agent.rules_content:
        (agent_dir / "RULES.md").write_text(registry_agent.rules_content, encoding="utf-8")

    # Write new skills
    skills_dest = _skills_dir(slot_id)
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    skills_dest.mkdir(parents=True, exist_ok=True)

    for skill in registry_agent.skills:
        skill_file = skills_dest / skill["name"]
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(skill["content"], encoding="utf-8")

    # If no skills provided by registry, write a minimal SKILL.md
    if not registry_agent.skills:
        (skills_dest / "SKILL.md").write_text(
            f"# {registry_agent.display_name}\n\n{registry_agent.description}\n",
            encoding="utf-8",
        )


def update_agent_yaml(slot_id: str, registry_agent: RegistryAgent) -> dict:
    """
    Update the agent.yaml entry for this slot with registry agent metadata.
    Returns the original agent config for the slot (before update).
    """
    yaml_path = _agent_yaml_path()
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    agents = config.get("agents", [])
    original = None
    for agent in agents:
        if agent["id"] == slot_id:
            original = {
                "name": agent.get("name", ""),
                "role": agent.get("role", ""),
                "capabilities": agent.get("capabilities", []),
                "tags": agent.get("tags", []),
            }
            # Update with registry agent data
            agent["name"] = registry_agent.display_name
            agent["role"] = registry_agent.role
            if registry_agent.capabilities:
                agent["capabilities"] = registry_agent.capabilities
            if registry_agent.tags:
                agent["tags"] = registry_agent.tags
            break

    if original is None:
        raise ValueError(f"Agent '{slot_id}' not found in agent.yaml")

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return original


def restore_agent(slot_id: str) -> dict:
    """
    Restore the original agent from backup.
    Returns the manifest data of what was restored.
    """
    validate_slot(slot_id)
    backup = _backup_dir(slot_id)
    manifest_path = _manifest_path(slot_id)

    if not manifest_path.exists():
        raise FileNotFoundError(f"No backup found for agent '{slot_id}'")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    agent_dir = _agents_dir(slot_id)

    # Restore prompt.md, SOUL.md, RULES.md
    for filename in ("prompt.md", "SOUL.md", "RULES.md"):
        backup_file = backup / filename
        if backup_file.exists():
            shutil.copy2(backup_file, agent_dir / filename)

    # Restore skills
    backup_skills = backup / "skills"
    skills_dest = _skills_dir(slot_id)
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    if backup_skills.exists():
        shutil.copytree(backup_skills, skills_dest)

    # Restore agent.yaml entry
    yaml_path = _agent_yaml_path()
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        if agent["id"] == slot_id:
            agent["name"] = manifest["original_name"]
            agent["role"] = manifest["original_role"]
            break

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Remove backup
    shutil.rmtree(backup)

    return manifest


def restart_agent_container(slot_id: str) -> None:
    """Restart the agent's Docker container via docker compose."""
    subprocess.run(
        ["docker", "compose", "restart", slot_id],
        cwd=str(PROJECT_ROOT),
        check=True,
        capture_output=True,
        timeout=60,
    )
