"""Registry client — fetch agent definitions from GitHub repos or gitagent registry."""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
import yaml


@dataclass
class RegistryAgent:
    """Normalized agent definition from a gitagent-compatible source."""
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


def _is_github_url(url: str) -> bool:
    """Check if the URL points to a GitHub repository."""
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    return url.startswith("github.com/")


def _parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub URL into (owner, repo)."""
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^github\.com/", "", url)
    # Remove trailing .git if present
    url = re.sub(r"\.git$", "", url)
    parts = url.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid GitHub URL. Expected format: 'github.com/owner/repo'. Got: '{url}'")
    return parts[0], parts[1]


def parse_registry_url(url: str) -> tuple[str, str]:
    """
    Parse a gitagent registry URL into (owner, agent_name).

    Accepts:
      - https://registry.gitagent.sh/agent/owner/name
      - registry.gitagent.sh/agent/owner/name
      - https://github.com/owner/repo
      - owner/name
    """
    url = url.strip().rstrip("/")

    if _is_github_url(url):
        return _parse_github_url(url)

    # Strip protocol
    url = re.sub(r"^https?://", "", url)

    # Strip registry domain + /agent/ prefix
    url = re.sub(r"^registry\.gitagent\.sh/agent/", "", url)

    parts = url.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid URL. Expected: 'owner/agent-name', "
            f"'github.com/owner/repo', or "
            f"'registry.gitagent.sh/agent/owner/agent-name'. Got: '{url}'"
        )
    return parts[0], parts[1]


async def _fetch_github_file(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> Optional[str]:
    """Fetch a file's content from a GitHub repo via raw URL. Returns None if not found."""
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
    resp = await client.get(raw_url)
    if resp.status_code == 404:
        # Try master branch as fallback
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
        resp = await client.get(raw_url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text


async def _list_github_dir(client: httpx.AsyncClient, owner: str, repo: str, path: str) -> list[dict]:
    """List files in a GitHub repo directory via API. Returns list of {name, path, type}."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = await client.get(api_url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


async def _fetch_from_github(url: str) -> RegistryAgent:
    """Fetch an agent definition from a GitHub repository."""
    owner, repo = _parse_github_url(url) if _is_github_url(url) else parse_registry_url(url)
    canonical_url = f"https://github.com/{owner}/{repo}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch agent.yaml (required)
        agent_yaml = await _fetch_github_file(client, owner, repo, "agent.yaml")
        if agent_yaml is None:
            agent_yaml = await _fetch_github_file(client, owner, repo, "agent.yml")
        if agent_yaml is None:
            raise ValueError(f"No agent.yaml or agent.yml found in {canonical_url}")

        agent_data = yaml.safe_load(agent_yaml)

        # Fetch prompt content — try prompt.md first, then SOUL.md
        prompt_content = await _fetch_github_file(client, owner, repo, "prompt.md")
        if prompt_content is None:
            soul_content = await _fetch_github_file(client, owner, repo, "SOUL.md")
            rules_content = await _fetch_github_file(client, owner, repo, "RULES.md")
            # Combine SOUL + RULES as the prompt if no prompt.md exists
            parts = []
            if soul_content:
                parts.append(soul_content)
            if rules_content:
                parts.append(rules_content)
            prompt_content = "\n\n---\n\n".join(parts) if parts else ""

        # Fetch skills from skills/ directory
        skills = []
        skill_names = agent_data.get("skills", [])
        if skill_names and isinstance(skill_names[0], str):
            # Skills are directory names under skills/
            for skill_name in skill_names:
                skill_dir_contents = await _list_github_dir(client, owner, repo, f"skills/{skill_name}")
                for item in skill_dir_contents:
                    if item.get("type") == "file" and item["name"].endswith(".md"):
                        content = await _fetch_github_file(client, owner, repo, item["path"])
                        if content:
                            skills.append({"name": f"{skill_name}/{item['name']}", "content": content})

        # If no skills fetched from dirs, check for a flat skills/ with .md files
        if not skills:
            skill_files = await _list_github_dir(client, owner, repo, "skills")
            for item in skill_files:
                if item.get("type") == "file" and item["name"].endswith(".md"):
                    content = await _fetch_github_file(client, owner, repo, item["path"])
                    if content:
                        skills.append({"name": item["name"], "content": content})

    return RegistryAgent(
        owner=owner,
        name=repo,
        display_name=agent_data.get("name", repo),
        role=agent_data.get("name", repo),
        description=agent_data.get("description", ""),
        prompt_content=prompt_content,
        skills=skills,
        capabilities=agent_data.get("capabilities", []),
        tags=agent_data.get("tags", []),
        source_url=canonical_url,
    )


async def _fetch_from_registry(owner: str, agent_name: str) -> RegistryAgent:
    """Fetch an agent definition from the gitagent registry API."""
    api_url = f"https://registry.gitagent.sh/api/v1/agents/{owner}/{agent_name}"
    canonical_url = f"https://registry.gitagent.sh/agent/{owner}/{agent_name}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

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


async def fetch_registry_agent(registry_url: str) -> RegistryAgent:
    """
    Fetch an agent definition from GitHub or the gitagent registry.

    Supports:
      - GitHub repo URLs: https://github.com/owner/repo
      - gitagent registry URLs: registry.gitagent.sh/agent/owner/name
      - Shorthand: owner/name (tries GitHub first, then registry)

    Args:
        registry_url: URL in any accepted format.

    Returns:
        RegistryAgent with all fields populated.
    """
    url = registry_url.strip().rstrip("/")

    # If it's explicitly a GitHub URL, go straight there
    if _is_github_url(url):
        return await _fetch_from_github(url)

    # If it's explicitly a registry URL, go straight there
    stripped = re.sub(r"^https?://", "", url)
    if stripped.startswith("registry.gitagent.sh/"):
        owner, agent_name = parse_registry_url(url)
        return await _fetch_from_registry(owner, agent_name)

    # Shorthand (owner/name) — try GitHub first, then registry
    owner, agent_name = parse_registry_url(url)
    try:
        return await _fetch_from_github(f"https://github.com/{owner}/{agent_name}")
    except (httpx.HTTPStatusError, ValueError):
        return await _fetch_from_registry(owner, agent_name)
