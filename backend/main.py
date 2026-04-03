"""Agent Swarm Studio — FastAPI Backend"""

import asyncio
import os
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import agents, chat, tasks, workflow
from ws.events import event_manager

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Load agents config ──────────────────────────────────────────
    config_path = os.getenv("AGENTS_CONFIG", "/app/agents.yaml")
    with open(config_path) as f:
        app.state.agents_config = yaml.safe_load(f)

    # ── Redis connection ────────────────────────────────────────────
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    app.state.redis = aioredis.from_url(redis_url, decode_responses=True)

    # ── Postgres connection pool ────────────────────────────────────
    db_url = os.getenv("DATABASE_URL", "postgresql://agentuser:agentpass@postgres:5432/agents")
    app.state.db = await asyncpg.create_pool(dsn=db_url, min_size=2, max_size=10)

    # ── Create tables ───────────────────────────────────────────────
    async with app.state.db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id          SERIAL PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                session_id  TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          UUID PRIMARY KEY,
                description TEXT NOT NULL,
                assign_to   TEXT NOT NULL DEFAULT 'orchestrator',
                status      TEXT NOT NULL DEFAULT 'pending',
                result      TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id          SERIAL PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS workflows (
                id          UUID PRIMARY KEY,
                company_url TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'running',
                task_ids    TEXT,
                synthesis   TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

    # ── Start Redis pub/sub → WebSocket broadcaster ─────────────────
    pubsub_task = asyncio.create_task(event_manager.subscribe(app.state.redis))

    yield

    # ── Cleanup ──────────────────────────────────────────────────────
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        pass
    await app.state.redis.aclose()
    await app.state.db.close()


app = FastAPI(
    title="Agent Swarm Studio",
    description="Orchestrate collaborative AI agent swarms",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(workflow.router, prefix="/workflow", tags=["workflow"])

# WebSocket endpoint lives in ws/events.py but is registered here
from ws.events import router as ws_router  # noqa: E402
app.include_router(ws_router, tags=["websocket"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@app.get("/config", tags=["config"])
async def get_config():
    return {
        "target_company_url": os.getenv("TARGET_COMPANY_URL", ""),
    }
