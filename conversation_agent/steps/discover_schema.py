"""Step: discover_schema — NL + context catalog tools → SchemaContext."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from context_agent import get_context_catalog_tools
from conversation_agent import config
from conversation_agent.models import SchemaContext
from conversation_agent.shared import (
    agent_trace_metadata,
    build_model,
    setup_langfuse,
)

STEP_NAME = "discover_schema"

INSTRUCTIONS = [
    "You select which ClickHouse tables, columns, and event names are relevant "
    "to the user's analytics question.",
    "ALWAYS call get_latest_context_items first (optionally filter kinds like "
    '"metric,funnel_step,entity,issue"). Use those items as the ONLY ground truth '
    "for business meaning, core funnel steps, metrics, joins, and known issues.",
    "If the question names a product feature (Express, Group, Forex, …), also call "
    "get_feature_meta(feature_id) for journey_order, ch_table, and event columns.",
    "Do NOT call publish_context_version — Conversation is read-only.",
    "Do not invent tables, columns, or events that are not present in tool results. "
    "There is no static schema document — catalog tools are the sole source.",
    "If get_latest_context_items returns no context_version / empty items, or tools "
    "fail, return a SchemaContext with empty tables and event_names, and explain "
    "the failure clearly in notes (do not guess schema).",
    "Return a SchemaContext JSON: database (if known from tool payloads), tables "
    "(each with name, columns [{name, type?}], event_names), optional notes and "
    "rationale.",
    "Prefer the minimum set of tables needed to answer the question. "
    "Include shared envelope columns from tool payloads (e.g. timestamp, user_id, "
    "device_type) when they are needed for filters, joins, or segments.",
    "When context_version is present in tool output, mention it in notes.",
]


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    return Agent(
        id=f"{config.AGENT_ID}-discover-schema",
        name="Discover Schema",
        model=build_model(),
        tools=[get_context_catalog_tools()],
        db=db,
        instructions=list(INSTRUCTIONS),
        output_schema=SchemaContext,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Select tables/columns/events using context catalog tools only",
        agent=build_agent(db=db),
    )
