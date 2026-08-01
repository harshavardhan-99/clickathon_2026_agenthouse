"""Step: generate_query — VizSpec → QuerySpec via funnel / windowFunnel skill."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from conversation_agent import config
from conversation_agent.models import QuerySpec
from conversation_agent.shared import (
    agent_trace_metadata,
    build_model,
    load_text_file,
    setup_langfuse,
)

STEP_NAME = "generate_query"

BASE_INSTRUCTIONS = [
    "Your input is a VizSpec (Pydantic JSON from plan_visualization).",
    "Follow the ClickHouse Funnel Analytics skill below in full before writing SQL.",
    "CRITICAL: Always query atlys.funnel_events. Do not use FROM events, and do not "
    "UNION per-event tables. Filter / windowFunnel conditions use the `event` column; "
    "time column is `timestamp`.",
    "For conversion funnels use windowFunnel() on atlys.funnel_events (correct partition "
    "key, window unit comment, ordered conditions, cumulative countIf for step reach).",
    "Emit exactly one SELECT (or WITH … SELECT) in QuerySpec.sql — no tools, do not execute.",
    "Prefer SQL that returns step / entities / conversion_from_start "
    "(plus segment_value when VizSpec asks for a segment cut).",
    "Also set QuerySpec.funnel, window_seconds, step_names, filters, tables_used "
    "(['funnel_events']), and caveats for the §5 funnel JSON contract.",
    "Do not invent event names absent from the VizSpec / skill / schema context.",
    "Companion metrics (latency, AOV, K-factor, churn counts) are NOT inside windowFunnel — "
    "note them in caveats; this step still returns one funnel query only.",
]


def load_query_skill() -> str:
    return load_text_file(config.GENERATE_QUERY_SKILL_PATH, label="generate_query skill")


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    skill_body = load_query_skill()
    return Agent(
        id=f"{config.AGENT_ID}-generate-query",
        name="Generate Query",
        model=build_model(),
        tools=[],
        db=db,
        instructions=[
            *BASE_INSTRUCTIONS,
            "Query skill:\n\n" + skill_body,
        ],
        output_schema=QuerySpec,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Generate windowFunnel ClickHouse SQL from VizSpec",
        agent=build_agent(db=db),
    )
