"""Registry client — fetch agent definitions from gitagent registry."""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class RegistryAgent:
    """Normalized agent definition from the gitagent registry."""
    owner: str
    name: str
    display_name: str
    role: str
    description: str
    prompt_content: str
    skills: list[dict] = field(default_factory=list)  # [{"name": str, "content": str}]
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_url: str = ""


def parse_registry_url(url: str) -> tuple[str, str]:
    """
    Parse a gitagent registry URL into (owner, agent_name).

    Accepts:
      - https://registry.gitagent.sh/agent/owner/name
      - registry.gitagent.sh/agent/owner/name
      - owner/name
    """
    url = url.strip().rstrip("/")

    # Strip protocol
    url = re.sub(r"^https?://", "", url)

    # Strip registry domain + /agent/ prefix
    url = re.sub(r"^registry\.gitagent\.sh/agent/", "", url)

    parts = url.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid registry URL. Expected format: 'owner/agent-name' or "
            f"'registry.gitagent.sh/agent/owner/agent-name'. Got: '{url}'"
        )
    return parts[0], parts[1]


async def fetch_registry_agent(registry_url: str) -> RegistryAgent:
    """
    Fetch an agent definition from the gitagent registry.

    Args:
        registry_url: Registry URL in any accepted format.

    Returns:
        RegistryAgent with all fields populated.

    Raises:
        ValueError: If the URL is malformed.
        httpx.HTTPStatusError: If the registry returns an error.
        httpx.ConnectError: If the registry is unreachable.
    """
    owner, agent_name = parse_registry_url(registry_url)
    api_url = f"https://registry.gitagent.sh/api/v1/agents/{owner}/{agent_name}"
    canonical_url = f"https://registry.gitagent.sh/agent/{owner}/{agent_name}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

    # Normalize registry response into our internal format
    agent_data = data if "agent" not in data else data["agent"]

    # Fetch prompt content if it's a URL reference
    prompt_content = agent_data.get("prompt", "") or agent_data.get("prompt_content", "")
    prompt_url = agent_data.get("prompt_url", "")
    if prompt_url and not prompt_content:
        async with httpx.AsyncClient(timeout=30.0) as client:
            prompt_resp = await client.get(prompt_url)
            prompt_resp.raise_for_status()
            prompt_content = prompt_resp.text

    # Fetch skill contents if they are URL references
    skills = []
    for skill in agent_data.get("skills", []):
        if isinstance(skill, str):
            # skill is a URL — fetch it
            async with httpx.AsyncClient(timeout=30.0) as client:
                skill_resp = await client.get(skill)
                skill_resp.raise_for_status()
                skill_name = skill.rsplit("/", 1)[-1]
                skills.append({"name": skill_name, "content": skill_resp.text})
        elif isinstance(skill, dict):
            skills.append({
                "name": skill.get("name", "SKILL.md"),
                "content": skill.get("content", ""),
            })

    return RegistryAgent(
        owner=owner,
        name=agent_name,
        display_name=agent_data.get("name", agent_name),
        role=agent_data.get("role", agent_name),
        description=agent_data.get("description", ""),
        prompt_content=prompt_content,
        skills=skills,
        capabilities=agent_data.get("capabilities", []),
        tags=agent_data.get("tags", []),
        source_url=canonical_url,
    )
