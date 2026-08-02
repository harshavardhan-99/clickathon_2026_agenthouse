"""run_analytics: deterministic SQL build + CH execute, with LLM/MCP fallback."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel

from conversation_agent.clickhouse_client import run_query as run_query_direct
from conversation_agent.models import ExecuteResult, QuerySpec, VizSpec
from conversation_agent.query_builders import (
    AnalyticsPlan,
    build_sql,
    plan_from_viz_spec,
)

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

_FENCE_RE = re.compile(
    r"^\s*```(?:json|sql)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _parse_viz(content: Any) -> VizSpec:
    if isinstance(content, VizSpec):
        return content
    if isinstance(content, BaseModel):
        return VizSpec.model_validate(content.model_dump())
    if isinstance(content, dict):
        return VizSpec.model_validate(content)
    if isinstance(content, str):
        return VizSpec.model_validate(json.loads(content))
    raise TypeError(f"Cannot parse VizSpec from {type(content)}")


def _strip_markdown_fence(text: str) -> str:
    raw = text.strip()
    matched = _FENCE_RE.match(raw)
    if matched:
        return matched.group(1).strip()
    # Partial fence (opening only) — common when model truncates
    if raw.startswith("```"):
        lines = raw.split("\n", 1)
        body = lines[1] if len(lines) > 1 else ""
        body = body.strip()
        if body.endswith("```"):
            body = body[: -3].rstrip()
        return body
    return raw


def _json_object_slice(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _extract_sql_field(text: str) -> str | None:
    """Pull QuerySpec.sql when JSON is invalid (e.g. LLM used \\')."""
    marker = re.search(r'"sql"\s*:\s*"', text)
    if not marker:
        return None
    i = marker.end()
    out: list[str] = []
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            escapes = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                '"': '"',
                "\\": "\\",
                "/": "/",
                "'": "'",  # invalid JSON, but models emit it
            }
            out.append(escapes.get(nxt, nxt))
            i += 2
            continue
        if ch == '"':
            break
        out.append(ch)
        i += 1
    sql = "".join(out).strip()
    return sql or None


def _coerce_query_spec(content: Any) -> QuerySpec:
    """Accept QuerySpec / dict / messy markdown+JSON string from generate_query."""
    if isinstance(content, QuerySpec):
        return content
    if isinstance(content, BaseModel):
        return QuerySpec.model_validate(content.model_dump())
    if isinstance(content, dict):
        return QuerySpec.model_validate(content)
    if not isinstance(content, str):
        raise TypeError(f"LLM returned unexpected type: {type(content)}")

    text = _strip_markdown_fence(content)
    candidate = _json_object_slice(text)

    for payload in (
        candidate,
        # Models often put \\' inside JSON strings (invalid) — soften to '
        candidate.replace("\\'", "'"),
    ):
        try:
            return QuerySpec.model_validate(json.loads(payload))
        except Exception:  # noqa: BLE001
            pass

    sql = _extract_sql_field(candidate) or _extract_sql_field(text)
    if sql:
        return QuerySpec(sql=sql)

    raise ValueError(
        "Could not coerce generate_query output to QuerySpec "
        f"(preview={content[:240]!r})"
    )


def run_deterministic(plan: AnalyticsPlan) -> ExecuteResult:
    built = build_sql(plan)
    columns, rows = run_query_direct(built.sql)
    return ExecuteResult(
        sql=built.sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        error=None,
        path="deterministic",
        caveats=built.caveats,
    )


async def run_llm_mcp_fallback(
    *,
    viz: VizSpec,
    user_question: str | None = None,
    mcp_tools: MCPTools | None = None,
    reason: str,
) -> ExecuteResult:
    """Existing path: LLM generate_query → execute (direct CH, else MCP)."""
    from conversation_agent.steps.generate_query import build_agent

    agent = build_agent(db=None)
    prompt_parts = [
        "Produce a QuerySpec for this VizSpec.",
        json.dumps(viz.model_dump(), default=str),
    ]
    if user_question:
        prompt_parts.insert(0, f"User question: {user_question}")
    run = await agent.arun("\n\n".join(prompt_parts))
    spec = _coerce_query_spec(run.content)

    sql = (spec.sql or "").strip()
    if not sql:
        raise RuntimeError("LLM QuerySpec.sql is empty")

    # Prefer direct ClickHouse client; MCP only if needed / provided
    try:
        from conversation_agent.clickhouse_client import run_query as run_query_direct

        columns, rows = run_query_direct(sql)
    except Exception:
        from conversation_agent.shared import run_query_via_mcp

        columns, rows = await run_query_via_mcp(sql, mcp_tools=mcp_tools)

    return ExecuteResult(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        error=None,
        path="llm_fallback",
        fallback_reason=reason,
        caveats=spec.caveats,
    )


async def run_analytics(
    *,
    viz: VizSpec | dict[str, Any] | None = None,
    plan: AnalyticsPlan | dict[str, Any] | None = None,
    user_question: str | None = None,
    mcp_tools: MCPTools | None = None,
    force_fallback: bool = False,
) -> ExecuteResult:
    """Build+execute via templates/CH client; on failure use LLM SQL + MCP."""
    viz_obj: VizSpec | None = None
    if viz is not None:
        try:
            viz_obj = _parse_viz(viz)
        except Exception:
            viz_obj = None

    reason = ""
    if not force_fallback:
        try:
            if plan is not None:
                plan_obj = (
                    plan
                    if isinstance(plan, AnalyticsPlan)
                    else AnalyticsPlan.model_validate(plan)
                )
            elif viz_obj is not None:
                plan_obj = plan_from_viz_spec(viz_obj)
            else:
                raise ValueError("Provide viz or plan")
            return run_deterministic(plan_obj)
        except Exception as exc:  # noqa: BLE001
            reason = str(exc) or repr(exc)
    else:
        reason = "force_fallback"

    if viz_obj is None and isinstance(viz, dict):
        # Best-effort VizSpec for fallback
        try:
            viz_obj = VizSpec(
                kind=str(viz.get("kind") or "table"),
                event_names=list(viz.get("event_names") or []),
                dimensions=list(viz.get("dimensions") or []),
                metric_names=list(viz.get("metric_names") or []),
                time_window=viz.get("time_window"),
                title=viz.get("title"),
            )
        except Exception:
            viz_obj = None

    if viz_obj is None:
        return ExecuteResult(
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error=(
                f"Deterministic path failed ({reason}) "
                "and no VizSpec for LLM fallback"
            ),
            path="failed",
            fallback_reason=reason,
        )

    try:
        return await run_llm_mcp_fallback(
            viz=viz_obj,
            user_question=user_question,
            mcp_tools=mcp_tools,
            reason=reason or "deterministic_failed",
        )
    except Exception as exc:  # noqa: BLE001
        detail = str(exc).strip() or repr(exc)
        return ExecuteResult(
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error=f"Fallback also failed: {detail}",
            path="failed",
            fallback_reason=reason,
        )
