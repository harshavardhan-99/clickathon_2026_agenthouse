"""API-level checks for chat formatting (uses ClickHouse for analytics run).

Run:
  PYENV_VERSION=clickathon python -m pytest tests/test_chat_format_api.py -q
"""

from __future__ import annotations

import asyncio
import json

from conversation_agent.chat_format import chat_result_to_text, format_chat_result
from conversation_agent.models import ExecuteResult, VizSpec
from conversation_agent.tools import get_analytics_tools


def test_deterministic_run_formats_to_blocks():
    async def _run():
        tools = get_analytics_tools()
        return await tools.run_analytics(
            kind="timeseries",
            event_names="purchase_completed",
            time_window="last_30_days",
            user_question="Revenue trend over time",
        )

    raw = asyncio.run(_run())
    exec_result = json.loads(raw)
    assert exec_result.get("error") in (None, ""), exec_result
    assert exec_result.get("path") == "deterministic"

    result = ExecuteResult.model_validate(exec_result)
    viz = VizSpec(
        kind="timeseries",
        title="Revenue Trend",
        metric_names=["revenue"],
        event_names=["purchase_completed"],
        time_window="last_30_days",
    )
    chat = format_chat_result(result, viz=viz)
    assert chat.mode == "blocks"
    text = chat_result_to_text(chat)
    payload = json.loads(text)
    assert payload["blocks"]
    insight = next(b for b in payload["blocks"] if b["type"] == "insight")
    assert insight["insight_type"] == "Trend"
    assert insight["metrics"][0]["metric_name"] == "revenue"


def test_force_fallback_formats_to_table():
    async def _run():
        tools = get_analytics_tools()
        return await tools.run_analytics(
            kind="timeseries",
            event_names="purchase_completed",
            time_window="last_30_days",
            user_question="Revenue trend over time",
            force_fallback=True,
            viz_json=json.dumps(
                {
                    "kind": "timeseries",
                    "event_names": ["purchase_completed"],
                    "metric_names": ["revenue"],
                    "time_window": "last_30_days",
                }
            ),
        )

    raw = asyncio.run(_run())
    exec_result = json.loads(raw)
    result = ExecuteResult.model_validate(exec_result)
    chat = format_chat_result(result, viz=None)
    assert chat.mode == "table"
    text = chat_result_to_text(chat)
    assert isinstance(text, str) and text
    assert "|" in text or "Analytics error" in text or "Fell back" in text
