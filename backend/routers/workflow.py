"""Workflow router — orchestrated multi-agent analysis with synthesis."""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import anthropic
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

# Agent-specific task descriptions keyed by agent ID
AGENT_TASKS = {
    "data-researcher": (
        "Research and profile the target company URL — company overview, products/services, "
        "team, funding, tech stack, GitHub presence, press coverage, competitive landscape"
    ),
    "lawyer": (
        "Legal scan of the target company URL — Terms of Service, privacy policy, "
        "compliance signals, regulatory risk, litigation history, IP portfolio, GDPR/CCPA status"
    ),
    "marketing": (
        "SEO and brand analysis of the target company URL — keyword landscape, content strategy, "
        "social media presence, brand positioning, competitive gaps, traffic signals"
    ),
    "sales": (
        "Revenue and sales intelligence from the target company URL — pricing model, ICP signals, "
        "growth indicators, market size, partnership opportunities, revenue estimation"
    ),
}


class AnalyzeRequest(BaseModel):
    company_url: str


class QuestionRequest(BaseModel):
    question: str
    company_url: str | None = None


@router.post("/analyze", response_model=Dict[str, Any], status_code=201)
async def start_analysis(body: AnalyzeRequest, request: Request):
    """
    Launch a full-spectrum analysis workflow.
    Creates one task per agent, tracks them as a workflow,
    and triggers orchestrator synthesis when all complete.
    """
    db = request.app.state.db
    redis = request.app.state.redis
    config = request.app.state.agents_config
    agents = config.get("agents", [])
    agent_ids = [a["id"] for a in agents]

    workflow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    task_ids = {}

    # Create a task for each agent
    for agent_id in agent_ids:
        task_id = str(uuid.uuid4())
        description = AGENT_TASKS.get(agent_id, f"Analyze {body.company_url}")
        full_description = f"{description}\n\nTarget: {body.company_url}"

        # Persist task
        await db.execute(
            """
            INSERT INTO tasks (id, description, assign_to, status, created_at, updated_at)
            VALUES ($1, $2, $3, 'pending', $4, $4)
            """,
            task_id, full_description, agent_id, now,
        )

        # Enqueue for agent
        payload = json.dumps({
            "task_id": task_id,
            "description": full_description,
            "assign_to": agent_id,
            "context": {"company_url": body.company_url},
        })
        await redis.lpush(f"tasks:{agent_id}", payload)

        # Publish event
        await redis.publish("agent:events", json.dumps({
            "type": "task_created",
            "task_id": task_id,
            "description": full_description[:80],
            "assigned_to": agent_id,
            "timestamp": now.isoformat(),
        }))

        task_ids[agent_id] = task_id

    # Persist workflow record
    await db.execute(
        """
        INSERT INTO workflows (id, company_url, task_ids, status, created_at, updated_at)
        VALUES ($1, $2, $3, 'running', $4, $4)
        """,
        workflow_id, body.company_url, json.dumps(task_ids), now,
    )

    # Publish workflow started event
    await redis.publish("agent:events", json.dumps({
        "type": "workflow_started",
        "workflow_id": workflow_id,
        "company_url": body.company_url,
        "agents": list(task_ids.keys()),
        "timestamp": now.isoformat(),
    }))

    # Launch background poller to watch for completion
    asyncio.create_task(
        _watch_workflow(workflow_id, task_ids, body.company_url, db, redis)
    )

    return {
        "workflow_id": workflow_id,
        "company_url": body.company_url,
        "status": "running",
        "tasks": task_ids,
    }


@router.post("/question", response_model=Dict[str, Any], status_code=201)
async def ask_all_agents(body: QuestionRequest, request: Request):
    """
    Dispatch a free-form question to all agents.
    Each agent answers from its own specialist perspective.
    Results are synthesized by the orchestrator when all complete.
    """
    db = request.app.state.db
    redis = request.app.state.redis
    config = request.app.state.agents_config
    agents = config.get("agents", [])
    agent_ids = [a["id"] for a in agents]

    workflow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    task_ids = {}

    url_context = ""
    if body.company_url:
        url_context = f"\n\nCompany context: {body.company_url}"

    for agent_id in agent_ids:
        task_id = str(uuid.uuid4())
        full_description = (
            f"Answer the following question from your specialist perspective "
            f"as the {agent_id} agent:\n\n{body.question}{url_context}"
        )

        await db.execute(
            """
            INSERT INTO tasks (id, description, assign_to, status, created_at, updated_at)
            VALUES ($1, $2, $3, 'pending', $4, $4)
            """,
            task_id, full_description, agent_id, now,
        )

        payload = json.dumps({
            "task_id": task_id,
            "description": full_description,
            "assign_to": agent_id,
            "context": {
                "question": body.question,
                "company_url": body.company_url or "",
            },
        })
        await redis.lpush(f"tasks:{agent_id}", payload)

        await redis.publish("agent:events", json.dumps({
            "type": "task_created",
            "task_id": task_id,
            "description": full_description[:80],
            "assigned_to": agent_id,
            "timestamp": now.isoformat(),
        }))

        task_ids[agent_id] = task_id

    # Persist workflow record
    company_label = body.company_url or "general"
    await db.execute(
        """
        INSERT INTO workflows (id, company_url, task_ids, status, created_at, updated_at)
        VALUES ($1, $2, $3, 'running', $4, $4)
        """,
        workflow_id, company_label, json.dumps(task_ids), now,
    )

    await redis.publish("agent:events", json.dumps({
        "type": "workflow_started",
        "workflow_id": workflow_id,
        "company_url": company_label,
        "agents": list(task_ids.keys()),
        "timestamp": now.isoformat(),
    }))

    asyncio.create_task(
        _watch_workflow(workflow_id, task_ids, company_label, db, redis)
    )

    return {
        "workflow_id": workflow_id,
        "question": body.question,
        "status": "running",
        "tasks": task_ids,
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_workflows(request: Request):
    """List recent workflows."""
    db = request.app.state.db
    rows = await db.fetch(
        """
        SELECT id::text, company_url, status, task_ids, synthesis, created_at, updated_at
        FROM workflows
        ORDER BY created_at DESC
        LIMIT 20
        """
    )
    result = []
    for r in rows:
        row = dict(r)
        row["task_ids"] = json.loads(row["task_ids"]) if row["task_ids"] else {}
        result.append(row)
    return result


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(workflow_id: str, request: Request):
    """Get a single workflow with its synthesis."""
    db = request.app.state.db
    row = await db.fetchrow(
        """
        SELECT id::text, company_url, status, task_ids, synthesis, created_at, updated_at
        FROM workflows
        WHERE id = $1
        """,
        workflow_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = dict(row)
    result["task_ids"] = json.loads(result["task_ids"]) if result["task_ids"] else {}
    return result


async def _watch_workflow(
    workflow_id: str,
    task_ids: Dict[str, str],
    company_url: str,
    db,
    redis,
):
    """Poll task statuses until all complete or any fail, then synthesize."""
    all_task_ids = list(task_ids.values())
    max_wait = 600  # 10 minutes
    elapsed = 0
    poll_interval = 5

    statuses = {}
    while elapsed < max_wait:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        rows = await db.fetch(
            """
            SELECT id::text, status FROM tasks
            WHERE id = ANY($1::uuid[])
            """,
            all_task_ids,
        )
        statuses = {str(r["id"]): r["status"] for r in rows}

        completed = sum(1 for s in statuses.values() if s == "completed")
        failed = sum(1 for s in statuses.values() if s == "failed")

        # Publish progress
        await redis.publish("agent:events", json.dumps({
            "type": "workflow_progress",
            "workflow_id": workflow_id,
            "completed": completed,
            "failed": failed,
            "total": len(all_task_ids),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        if completed + failed == len(all_task_ids):
            break

    timed_out_agents = []
    if completed + failed < len(all_task_ids):
        timed_out_agents = [
            agent_id for agent_id, task_id in task_ids.items()
            if statuses.get(task_id) not in {"completed", "failed"}
        ]
        await redis.publish("agent:events", json.dumps({
            "type": "workflow_timeout",
            "workflow_id": workflow_id,
            "timed_out_agents": timed_out_agents,
            "completed": completed,
            "failed": failed,
            "total": len(all_task_ids),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    # All done (or timed out) — gather ALL task history for full context
    now = datetime.now(timezone.utc)

    # Current workflow results (primary focus)
    current_rows = await db.fetch(
        """
        SELECT assign_to, description, status, result FROM tasks
        WHERE id = ANY($1::uuid[])
        """,
        all_task_ids,
    )

    # All prior completed tasks across the swarm (historical context)
    history_rows = await db.fetch(
        """
        SELECT assign_to, description, result, updated_at FROM tasks
        WHERE status = 'completed'
          AND result IS NOT NULL
          AND id != ALL($1::uuid[])
        ORDER BY updated_at DESC
        LIMIT 20
        """,
        all_task_ids,
    )

    # Build current workflow findings
    current_findings = []
    for r in current_rows:
        current_findings.append(
            f"## {r['assign_to'].upper()} ({r['status']})\n\n"
            f"{r['result'][:4000] if r['result'] else '(no output)'}"
        )

    # Build historical context
    history_context = ""
    if history_rows:
        history_parts = []
        for r in reversed(history_rows):
            ts = r["updated_at"].strftime("%Y-%m-%d %H:%M UTC") if r["updated_at"] else ""
            history_parts.append(
                f"### [{r['assign_to']}] {r['description'][:100]}\n"
                f"Completed: {ts}\n"
                f"{r['result'][:2000]}"
            )
        history_context = (
            "\n\n---\n\n## PRIOR TASK HISTORY (all agents, older analyses)\n"
            "Use this to identify patterns, track changes over time, and build on prior findings.\n\n"
            + "\n\n---\n\n".join(history_parts)
        )

    timeout_note = ""
    if timed_out_agents:
        timeout_note = (
            "\n\nIMPORTANT: This workflow hit the watcher timeout before every agent finished. "
            f"Treat these agents as incomplete and call out the gap explicitly: {', '.join(timed_out_agents)}."
        )

    synthesis_prompt = (
        f"You are the Orchestrator for a Business Intelligence Swarm. "
        f"Your team of 4 specialist agents just analyzed {company_url}.\n\n"
        f"Below are their CURRENT findings, followed by all PRIOR task history from the swarm.\n"
        f"Synthesize everything into a single, cohesive executive briefing.\n"
        f"Structure: Executive Summary, Key Findings, Risk Assessment, Opportunities, "
        f"Recommended Actions, Changes From Prior Analysis (if applicable).\n"
        f"Be thorough but concise. Cross-reference findings across agents where they "
        f"overlap or conflict. Note any evolution from prior analyses."
        + timeout_note
        + "\n\n## CURRENT ANALYSIS RESULTS\n\n"
        + "\n\n---\n\n".join(current_findings)
        + history_context
    )

    # Call LLM for synthesis
    try:
        oauth_key = os.getenv("ANTHROPIC_OAUTH_KEY", "").strip()
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        proxy_url = os.getenv("CLAUDE_PROXY_URL", "http://claude-proxy:8319")

        if oauth_key:
            client = anthropic.Anthropic(base_url=proxy_url, api_key="oauth-proxy")
        elif api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            raise RuntimeError(
                "No Anthropic credentials configured. Set ANTHROPIC_API_KEY or ANTHROPIC_OAUTH_KEY."
            )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system="You are the Orchestrator — a strategic synthesizer who combines multi-agent intelligence into actionable executive briefings.",
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        synthesis = response.content[0].text
    except Exception as e:
        synthesis = f"Synthesis failed: {e}"

    workflow_status = "completed"
    if timed_out_agents or failed:
        workflow_status = "completed_with_gaps"

    # Save synthesis
    await db.execute(
        """
        UPDATE workflows
        SET status = $1, synthesis = $2, updated_at = $3
        WHERE id = $4
        """,
        workflow_status, synthesis, now, workflow_id,
    )

    # Also store synthesis as a task result for visibility in the UI
    synth_task_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO tasks (id, description, assign_to, status, result, created_at, updated_at)
        VALUES ($1, $2, 'orchestrator', 'completed', $3, $4, $4)
        """,
        synth_task_id,
        f"Orchestrator synthesis for {company_url}",
        synthesis,
        now,
    )

    # Publish completion events
    await redis.publish("agent:events", json.dumps({
        "type": "workflow_completed",
        "workflow_id": workflow_id,
        "company_url": company_url,
        "status": workflow_status,
        "synthesis_preview": synthesis[:300],
        "timestamp": now.isoformat(),
    }))
    await redis.publish("agent:events", json.dumps({
        "type": "task_completed",
        "agent_id": "orchestrator",
        "task_id": synth_task_id,
        "result_preview": synthesis[:300],
        "timestamp": now.isoformat(),
    }))
