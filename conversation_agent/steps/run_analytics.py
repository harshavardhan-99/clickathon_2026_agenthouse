"""Step: run_analytics — deterministic build+CH, fallback LLM+MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from agno.workflow import Step
from agno.workflow.types import StepInput, StepOutput

from conversation_agent.analytics import run_analytics

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

STEP_NAME = "run_analytics"


def build_step(*, mcp_tools: Optional[MCPTools] = None) -> Step:
    async def _run(step_input: StepInput) -> StepOutput:
        prior = step_input.get_step_output("plan_visualization")
        content = prior.content if prior is not None else step_input.previous_step_content
        question = None
        if isinstance(step_input.input, str):
            question = step_input.input
        elif step_input.input is not None:
            question = str(step_input.input)

        result = await run_analytics(
            viz=content,
            user_question=question,
            mcp_tools=mcp_tools,
        )
        ok = result.error is None
        return StepOutput(content=result, success=ok, error=result.error)

    return Step(
        name=STEP_NAME,
        description=(
            "Build SQL via templates + execute with clickhouse-connect; "
            "fallback to LLM SQL + ClickHouse MCP"
        ),
        executor=_run,
    )
