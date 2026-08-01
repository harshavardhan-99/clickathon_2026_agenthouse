"""Step: discover_schema — NL question + context file → SchemaContext (no tools)."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from conversation_agent import config
from conversation_agent.models import SchemaContext
from conversation_agent.shared import build_model, load_text_file, model_trace_labels, setup_langfuse

STEP_NAME = "discover_schema"

INSTRUCTIONS = [
    "You select which ClickHouse tables, columns, and event names are relevant "
    "to the user's analytics question.",
    "Use ONLY the schema context document below as ground truth. "
    "Do not invent tables, columns, or events that are not listed there.",
    "Return a SchemaContext JSON: database (if known), tables (each with name, "
    "columns [{name, type?}], event_names), optional notes and rationale.",
    "Prefer the minimum set of tables needed to answer the question. "
    "Include shared envelope columns (e.g. timestamp, user_id, device_type) when "
    "they are needed for filters, joins, or segments.",
]


def load_schema_context() -> str:
    return load_text_file(config.SCHEMA_CONTEXT_PATH, label="schema context")


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    labels = model_trace_labels()
    context_body = load_schema_context()
    return Agent(
        id=f"{config.AGENT_ID}-discover-schema",
        name="Discover Schema",
        model=build_model(),
        tools=[],
        db=db,
        instructions=[
            *INSTRUCTIONS,
            "Schema context (ground truth):\n\n" + context_body,
        ],
        output_schema=SchemaContext,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata={
            "model_provider": labels["model_provider"],
            "model_id": labels["model_id"],
            "model": labels["model"],
            "step": STEP_NAME,
        },
    )


def build_step(*, db: Any = None) -> Step:
    return Step(
        name=STEP_NAME,
        description="Select relevant tables/columns/events from schema context",
        agent=build_agent(db=db),
    )
