"""Step: run_analytics — deterministic build+CH, fallback LLM+MCP.

Workflow chat output is massaged (blocks config vs Markdown table); the
underlying ``run_analytics`` still returns ``ExecuteResult`` for tools/API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from agno.workflow import Step
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel

from conversation_agent.analytics import run_analytics
from conversation_agent.chat_format import format_chat_result
from conversation_agent.models import VizSpec

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

STEP_NAME = "run_analytics"


def _as_viz(content: Any) -> VizSpec | None:
    if content is None:
        return None
    if isinstance(content, VizSpec):
        return content
    try:
        if isinstance(content, BaseModel):
            return VizSpec.model_validate(content.model_dump())
        if isinstance(content, dict):
            return VizSpec.model_validate(content)
        if isinstance(content, str):
            return VizSpec.model_validate_json(content)
    except Exception:  # noqa: BLE001
        return None
    return None


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
        chat = format_chat_result(result, viz=_as_viz(content))
        ok = result.error is None
        return StepOutput(content=chat, success=ok, error=result.error)

    return Step(
        name=STEP_NAME,
        description=(
            "Build SQL via templates + execute with clickhouse-connect; "
            "fallback to LLM SQL + ClickHouse MCP; format chat as blocks or table"
        ),
        executor=_run,
    )
