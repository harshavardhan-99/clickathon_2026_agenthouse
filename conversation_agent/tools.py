"""Agno toolkit: single run_analytics tool (deterministic + LLM/MCP fallback)."""

from __future__ import annotations

import json
from typing import Optional

from agno.tools import Toolkit

from conversation_agent.analytics import run_analytics
from conversation_agent.query_builders import AnalyticsPlan


class AnalyticsTools(Toolkit):
    """One fat tool: template SQL + clickhouse-connect, else LLM + MCP."""

    def __init__(self):
        super().__init__(name="analytics", tools=[self.run_analytics])

    async def run_analytics(
        self,
        kind: str,
        event_names: Optional[str] = None,
        dimensions: Optional[str] = None,
        time_window: Optional[str] = "last_30_days",
        window_seconds: int = 86400,
        filters_json: Optional[str] = None,
        limit: int = 20,
        viz_json: Optional[str] = None,
        user_question: Optional[str] = None,
        force_fallback: bool = False,
    ) -> str:
        """Run ClickHouse analytics: build SQL + execute (or LLM/MCP fallback).

        Prefer structured args. kind: funnel | timeseries | breakdown | metric |
        top_n | comparison.

        Args:
            kind: Analytics pattern key.
            event_names: Comma-separated event names (funnel order for funnels;
                for metric rates: numerator,denominator).
            dimensions: Comma-separated group-by columns
                (device_type, os, geoip_country_code, destination).
            time_window: e.g. last_30_days.
            window_seconds: windowFunnel window (funnel kind).
            filters_json: Optional JSON object of equality filters.
            limit: Max rows for breakdown/top_n.
            viz_json: Optional full VizSpec JSON (used for LLM fallback).
            user_question: Original NL question (helps LLM fallback).
            force_fallback: Skip builders; use LLM + MCP only.
        """
        events = [e.strip() for e in (event_names or "").split(",") if e.strip()]
        dims = [d.strip() for d in (dimensions or "").split(",") if d.strip()]
        filters: dict = {}
        if filters_json:
            parsed = json.loads(filters_json)
            if not isinstance(parsed, dict):
                return json.dumps({"error": "filters_json must be a JSON object"})
            filters = parsed

        viz = None
        if viz_json:
            viz = json.loads(viz_json)
        else:
            viz = {
                "kind": kind,
                "event_names": events,
                "dimensions": dims,
                "time_window": time_window,
                "metric_names": [],
            }

        plan = None
        try:
            plan = AnalyticsPlan(
                kind=kind,  # type: ignore[arg-type]
                event_names=events,
                dimensions=dims,
                time_window=time_window,
                window_seconds=window_seconds,
                filters=filters,
                limit=limit,
            )
        except Exception:
            plan = None

        result = await run_analytics(
            plan=plan,
            viz=viz,
            user_question=user_question,
            force_fallback=force_fallback,
        )
        return result.model_dump_json()


def get_analytics_tools() -> AnalyticsTools:
    return AnalyticsTools()
