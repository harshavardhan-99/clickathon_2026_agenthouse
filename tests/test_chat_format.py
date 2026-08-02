"""Unit tests for chat output massaging (no ClickHouse)."""

from __future__ import annotations

from conversation_agent.chat_format import (
    blocks_from_viz,
    chat_result_to_text,
    format_chat_result,
    rows_to_markdown_table,
)
from conversation_agent.models import ExecuteResult, VizSpec


def test_markdown_table_basic():
    md = rows_to_markdown_table(
        ["day", "events"],
        [["2026-06-01", 30], ["2026-06-02", 29]],
    )
    assert "| day | events |" in md
    assert "| 2026-06-01 | 30 |" in md


def test_blocks_from_timeseries_viz():
    viz = VizSpec(
        kind="timeseries",
        title="Revenue trend",
        metric_names=["revenue"],
        event_names=["purchase_completed"],
        time_window="last_30_days",
    )
    resp = blocks_from_viz(viz)
    assert len(resp.blocks) >= 2
    insight = next(b for b in resp.blocks if getattr(b, "type", None) == "insight")
    assert insight.insight_type == "Trend"
    assert insight.metrics[0].metric_name == "revenue"
    assert insight.dimensions == []


def test_blocks_ranking_requires_one_dim():
    viz = VizSpec(
        kind="breakdown",
        dimensions=["device_type"],
        metric_names=["users"],
        event_names=["purchase_completed"],
    )
    insight = next(
        b for b in blocks_from_viz(viz).blocks if getattr(b, "type", None) == "insight"
    )
    assert insight.insight_type == "Ranking"
    assert insight.dimensions == ["channel"]


def test_format_deterministic_emits_blocks():
    viz = VizSpec(
        kind="timeseries",
        metric_names=["purchases"],
        event_names=["purchase_completed"],
    )
    exec_result = ExecuteResult(
        sql="SELECT 1",
        columns=["x"],
        rows=[[1]],
        row_count=1,
        path="deterministic",
    )
    chat = format_chat_result(exec_result, viz=viz)
    assert chat.mode == "blocks"
    assert chat.blocks is not None
    text = chat_result_to_text(chat)
    assert '"insight_type": "Trend"' in text or '"insight_type":"Trend"' in text


def test_format_fallback_emits_markdown_table():
    exec_result = ExecuteResult(
        sql="SELECT day, n FROM t",
        columns=["day", "n"],
        rows=[["2026-06-01", 10]],
        row_count=1,
        path="llm_fallback",
        fallback_reason="No deterministic builder",
    )
    chat = format_chat_result(exec_result, viz=None)
    assert chat.mode == "table"
    text = chat_result_to_text(chat)
    assert "| day | n |" in text
    assert "```sql" in text
