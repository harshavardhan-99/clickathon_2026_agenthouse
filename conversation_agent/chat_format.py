"""Minimal chat output massaging: ExecuteResult → blocks JSON or Markdown table.

Keeps the analytics pipeline unchanged; only reshapes what LibreChat sees.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from conversation_agent.catalog import FUNNEL_STAGE_METRICS, METRICS, resolve_metric
from conversation_agent.models import (
    AgentChatResult,
    AnalyticsInsightBlock,
    AnalyticsMetric,
    AnalyticsQueryResponse,
    AnalyticsTextBlock,
    ExecuteResult,
    VizSpec,
)

_DEFAULT_FROM = "2026-01-01"
_DEFAULT_TO = "2026-06-30"
_DIM_ALIAS = {
    "geoip_country_code": "country",
    "device_type": "channel",
}
_MAX_TABLE_ROWS = 50


def rows_to_markdown_table(
    columns: list[str],
    rows: list[list[Any]],
    *,
    max_rows: int = _MAX_TABLE_ROWS,
) -> str:
    """GFM Markdown table (LibreChat renders this; raw HTML does not)."""
    if not columns:
        return "_No columns._"

    def cell(value: Any) -> str:
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\n", " ").strip()

    header = "| " + " | ".join(cell(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(cell(v) for v in row) + " |"
        for row in rows[:max_rows]
    ]
    parts = [header, sep, *body]
    if len(rows) > max_rows:
        parts.append(f"\n_Showing {max_rows} of {len(rows)} rows._")
    return "\n".join(parts)


def _window_dates(time_window: Optional[str]) -> tuple[str, str]:
    """Best-effort calendar bounds for block metadata (hackathon defaults OK)."""
    raw = (time_window or "").strip().lower().replace(" ", "_")
    if raw.startswith("last_") and raw.endswith("_days"):
        try:
            days = int(raw.removeprefix("last_").removesuffix("_days"))
            end = date(2026, 6, 30)
            start = end - timedelta(days=max(days - 1, 0))
            return start.isoformat(), end.isoformat()
        except ValueError:
            pass
    return _DEFAULT_FROM, _DEFAULT_TO


def _metric(key: str) -> AnalyticsMetric:
    m = resolve_metric(key)
    if m:
        return AnalyticsMetric(metric_name=m.key, metric_label=m.label)
    return AnalyticsMetric(metric_name=key, metric_label=key.replace("_", " ").title())


def _pick_metrics(viz: VizSpec) -> list[AnalyticsMetric]:
    keys = [k for k in viz.metric_names if k in METRICS]
    if keys:
        return [_metric(k) for k in keys]
    events = set(viz.event_names or [])
    if "purchase_completed" in events or any(
        "purchase" in (m or "").lower() for m in viz.metric_names
    ):
        return [_metric("purchases")]
    if any("revenue" in (m or "").lower() for m in viz.metric_names):
        return [_metric("revenue")]
    return [_metric("users")]


def _catalog_dims(dims: list[str]) -> list[str]:
    return [_DIM_ALIAS.get(d, d) for d in dims]


def blocks_from_viz(viz: VizSpec) -> AnalyticsQueryResponse:
    """Map a VizSpec to metadata-only insight blocks (no chart points)."""
    kind = (viz.kind or "timeseries").strip().lower()
    from_t, to_t = _window_dates(viz.time_window)
    metrics = _pick_metrics(viz)
    dims = _catalog_dims(list(viz.dimensions or []))
    title = viz.title or "Analytics"

    if kind == "funnel":
        insight = AnalyticsInsightBlock(
            title=title,
            caption=viz.rationale,
            insight_type="Funnel",
            metrics=[_metric(k) for k in FUNNEL_STAGE_METRICS],
            dimensions=dims[:1],
            fromTime=from_t,
            toTime=to_t,
            timeGrain="DAILY",
        )
    elif kind in {"breakdown", "top_n", "topn", "table"} and len(dims) >= 1:
        insight = AnalyticsInsightBlock(
            title=title,
            caption=viz.rationale,
            insight_type="Ranking",
            metrics=metrics,
            dimensions=dims[:1],
            fromTime=from_t,
            toTime=to_t,
            timeGrain="DAILY",
        )
    elif kind == "comparison" and len(dims) >= 2:
        insight = AnalyticsInsightBlock(
            title=title,
            caption=viz.rationale,
            insight_type="Pivot",
            metrics=metrics,
            dimensions=dims[:2],
            fromTime=from_t,
            toTime=to_t,
            timeGrain="DAILY",
        )
    else:
        insight = AnalyticsInsightBlock(
            title=title,
            caption=viz.rationale,
            insight_type="Trend",
            metrics=metrics,
            dimensions=[],
            fromTime=from_t,
            toTime=to_t,
            timeGrain="DAILY",
        )

    text = AnalyticsTextBlock(
        text=f"Deterministic query OK — insight config for: {title}",
    )
    return AnalyticsQueryResponse(blocks=[text, insight])


def format_chat_result(
    result: ExecuteResult,
    *,
    viz: VizSpec | None = None,
) -> AgentChatResult:
    """Deterministic success → blocks config; otherwise Markdown table."""
    path = result.path or ""
    if result.error is None and path == "deterministic" and viz is not None:
        try:
            blocks = blocks_from_viz(viz)
            return AgentChatResult(
                mode="blocks",
                blocks=blocks,
                sql=result.sql,
                path=path,
                caveats=result.caveats,
            )
        except Exception as exc:  # noqa: BLE001
            table = rows_to_markdown_table(result.columns, result.rows)
            return AgentChatResult(
                mode="table",
                table_markdown=table,
                sql=result.sql,
                path=path,
                fallback_reason=f"blocks_mapping_failed: {exc}",
                caveats=result.caveats,
            )

    intro = "Query results"
    if result.fallback_reason:
        intro = f"Fell back to LLM SQL ({result.fallback_reason}). Results:"
    if result.error:
        intro = f"Analytics error: {result.error}"

    table = rows_to_markdown_table(result.columns, result.rows)
    md = f"{intro}\n\n{table}" if result.columns else intro
    if result.sql:
        md += f"\n\n```sql\n{result.sql.strip()}\n```"

    return AgentChatResult(
        mode="table",
        table_markdown=md,
        sql=result.sql or None,
        path=path or None,
        fallback_reason=result.fallback_reason,
        caveats=result.caveats,
    )


def chat_result_to_text(result: AgentChatResult) -> str:
    """String LibreChat bridge puts in assistant `content`."""
    if result.mode == "blocks" and result.blocks is not None:
        return json.dumps(result.blocks.model_dump(mode="json"), indent=2, default=str)
    return (result.table_markdown or "").strip()
