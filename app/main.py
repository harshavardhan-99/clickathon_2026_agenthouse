"""Shared FastAPI + Agno AgentOS host (scaffold).

Wire Instrumentation / Context / Conversation agents here as they land.
Start locally: ``uv run uvicorn app.main:app --reload --port 8000``
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Click-a-thon AgentHouse",
    version="0.1.0",
    description="FastAPI host for Agno AgentOS agents (Instrumentation, Context, Conversation).",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# When agents exist:
# from agno.os import AgentOS
# agent_os = AgentOS(id="agenthouse", agents=[...], base_app=app)
# app = agent_os.get_app()
