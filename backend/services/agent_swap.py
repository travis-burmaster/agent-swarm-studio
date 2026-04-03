"""Agent swap service — backup, replace, and restore agent slots."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from services.registry_client import RegistryAgent

# Paths relative to the project root (mapped via Docker volumes or local dev)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # agent-swarm-studio/


def _agents_dir(slot_id: str) -> Path:
    return PROJECT_ROOT / "agents" / slot_id


def _skills_dir(slot_id: str) -> Path:
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
    """Back up the current agent's prompt and skills before replacement."""
    validate_slot(slot_id)
    backup = _backup_dir(slot_id)

    # Remove previous backup if it exists
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)

    # Back up prompt.md
    prompt_src = _agents_dir(slot_id) / "prompt.md"
    if prompt_src.exists():
        shutil.copy2(prompt_src, backup / "prompt.md")

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
    """Write the registry agent's prompt and skills to the agent slot."""
    validate_slot(slot_id)

    # Write new prompt.md
    prompt_dest = _agents_dir(slot_id) / "prompt.md"
    prompt_dest.write_text(registry_agent.prompt_content, encoding="utf-8")

    # Write new skills
    skills_dest = _skills_dir(slot_id)
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    skills_dest.mkdir(parents=True, exist_ok=True)

    for skill in registry_agent.skills:
        skill_file = skills_dest / skill["name"]
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

    # Restore prompt.md
    backup_prompt = backup / "prompt.md"
    if backup_prompt.exists():
        shutil.copy2(backup_prompt, _agents_dir(slot_id) / "prompt.md")

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
