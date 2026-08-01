"""Step: plan_visualization — SchemaContext → VizSpec (no tools)."""

from __future__ import annotations

from typing import Any

from agno.agent import Agent
from agno.workflow import Step

from conversation_agent import config
from conversation_agent.models import VizSpec
from conversation_agent.shared import build_model, model_trace_labels, setup_langfuse

STEP_NAME = "plan_visualization"

INSTRUCTIONS = [
    "You plan one visualization from a SchemaContext (tables, columns, event names) "
    "and the user's analytics question.",
    "Only use fields present in the schema. Do not invent columns or events.",
    "Return a VizSpec JSON with: kind (visualization type), optional title, "
    "metric_names, dimensions, event_names, time_window, rationale.",
    "Viz kind is a stub until types are finalized — pick the best fit among: "
    "timeseries, breakdown, comparison, table, funnel.",
    "Prefer segment dimensions already in the schema when relevant "
    "(device_type, geoip_country_code, destination).",
]


def build_agent(*, db: Any = None) -> Agent:
    setup_langfuse()
    labels = model_trace_labels()
    return Agent(
        id=f"{config.AGENT_ID}-plan-visualization",
        name="Plan Visualization",
        model=build_model(),
        tools=[],
        db=db,
        instructions=list(INSTRUCTIONS),
        output_schema=VizSpec,
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
        description="Choose visualization type and params from schema",
        agent=build_agent(db=db),
    )
