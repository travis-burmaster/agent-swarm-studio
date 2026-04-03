#!/usr/bin/env python3
"""CLI tool for replacing/restoring agent slots from the gitagent registry.

Usage:
  python -m scripts.replace_agent --slot sales --registry shreyas-lyzr/quant-sim
  python -m scripts.replace_agent --slot sales --restore
  python -m scripts.replace_agent --slot sales --info
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

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
from services.registry_client import fetch_registry_agent


async def do_replace(slot: str, registry_url: str) -> None:
    print(f"Fetching agent from registry: {registry_url}")
    registry_agent = await fetch_registry_agent(registry_url)
    print(f"  Found: {registry_agent.display_name} ({registry_agent.role})")

    # Get original info from agent.yaml
    import yaml
    from services.agent_swap import _agent_yaml_path
    with open(_agent_yaml_path()) as f:
        config = yaml.safe_load(f)
    agent_cfg = next((a for a in config.get("agents", []) if a["id"] == slot), None)
    if not agent_cfg:
        print(f"Error: agent '{slot}' not found in agent.yaml")
        sys.exit(1)

    original_name = agent_cfg.get("name", "")
    original_role = agent_cfg.get("role", "")

    print(f"Backing up current agent: {original_name}")
    backup_agent(slot)
    write_manifest(slot, original_name, original_role, registry_agent)

    print("Writing replacement files...")
    replace_agent_files(slot, registry_agent)
    update_agent_yaml(slot, registry_agent)

    print(f"Restarting container: {slot}")
    try:
        restart_agent_container(slot)
        print("Done! Container is restarting.")
    except Exception as e:
        print(f"Warning: container restart failed ({e}). You may need to restart manually:")
        print(f"  docker compose restart {slot}")


def do_restore(slot: str) -> None:
    info = get_replacement_info(slot)
    if not info["is_replaced"]:
        print(f"Agent '{slot}' has not been replaced — nothing to restore.")
        return

    print(f"Restoring original agent: {info['original_name']}")
    restore_agent(slot)

    print(f"Restarting container: {slot}")
    try:
        restart_agent_container(slot)
        print("Done! Original agent restored and container is restarting.")
    except Exception as e:
        print(f"Warning: container restart failed ({e}). Restart manually:")
        print(f"  docker compose restart {slot}")


def do_info(slot: str) -> None:
    info = get_replacement_info(slot)
    print(json.dumps(info, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Replace or restore agent slots from gitagent registry")
    parser.add_argument("--slot", required=True, help="Agent slot ID (lawyer, data-researcher, marketing, sales)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--registry", help="Registry agent reference (e.g. shreyas-lyzr/quant-sim)")
    group.add_argument("--restore", action="store_true", help="Restore the original agent from backup")
    group.add_argument("--info", action="store_true", help="Show replacement status")
    args = parser.parse_args()

    try:
        validate_slot(args.slot)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.registry:
        asyncio.run(do_replace(args.slot, args.registry))
    elif args.restore:
        do_restore(args.slot)
    elif args.info:
        do_info(args.slot)


if __name__ == "__main__":
    main()
