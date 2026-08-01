"""Pydantic contracts for the Visualization Agent workflow."""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Step 1 — discover_schema
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    name: str = Field(..., description="Column name")
    type: Optional[str] = Field(None, description="ClickHouse type if known")


class TableSchema(BaseModel):
    name: str = Field(..., description="Table name")
    columns: list[ColumnInfo] = Field(
        default_factory=list,
        description="Relevant columns for the question",
    )
    event_names: list[str] = Field(
        default_factory=list,
        description="Event names present in / represented by this table",
    )


class SchemaContext(BaseModel):
    """Tables / columns / events selected for the analytics question."""

    database: Optional[str] = Field(None, description="Database name if known")
    tables: list[TableSchema] = Field(
        ...,
        description="Relevant tables with columns and event names",
    )
    notes: Optional[str] = Field(None, description="Join / funnel / caveats")
    rationale: Optional[str] = Field(
        None,
        description="Why these tables were selected for the question",
    )


# ---------------------------------------------------------------------------
# Step 2 — plan_visualization (stub until viz-type structure is finalized)
# ---------------------------------------------------------------------------


class VizSpec(BaseModel):
    """Visualization plan — shape is a stub; swap when viz types are defined."""

    kind: str = Field(
        ...,
        description=(
            "Visualization type key (stub). Examples until finalized: "
            "timeseries, breakdown, comparison, table, funnel"
        ),
    )
    title: Optional[str] = Field(None, description="Short chart title")
    metric_names: list[str] = Field(
        default_factory=list,
        description="Metrics the visualization should show",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Slice / group-by dimensions",
    )
    event_names: list[str] = Field(
        default_factory=list,
        description="Events involved in the viz",
    )
    time_window: Optional[str] = Field(
        None,
        description="Requested time window, e.g. last_30_days",
    )
    rationale: Optional[str] = Field(
        None,
        description="Why this viz type fits the question and schema",
    )


# ---------------------------------------------------------------------------
# Step 3 — generate_query
# ---------------------------------------------------------------------------


class QuerySpec(BaseModel):
    """Single ClickHouse SELECT to execute (funnel / analytics)."""

    sql: str = Field(..., description="Exactly one aggregate SELECT (or WITH … SELECT)")
    tables_used: list[str] = Field(
        default_factory=list,
        description="Tables referenced in the SQL",
    )
    funnel: Optional[str] = Field(
        None,
        description="Funnel id for viz contract, e.g. express_checkout",
    )
    window_seconds: Optional[int] = Field(
        None,
        description="windowFunnel window in seconds (when event_time is DateTime)",
    )
    step_names: list[str] = Field(
        default_factory=list,
        description="Ordered funnel step event_name values",
    )
    filters: Optional[dict[str, Any]] = Field(
        None,
        description="Filters for viz contract, e.g. start_date, end_date, segment",
    )
    caveats: Optional[str] = Field(
        None,
        description="Limitations, timestamp unit, companion metrics not in this SQL",
    )


# ---------------------------------------------------------------------------
# Step 4 — execute
# ---------------------------------------------------------------------------


class ExecuteResult(BaseModel):
    """Deterministic query execution result."""

    sql: str = Field(..., description="SQL that was run")
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(
        default_factory=list,
        description="Row values aligned with columns",
    )
    row_count: int = Field(0, description="Number of rows returned")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    path: Optional[str] = Field(
        None,
        description="deterministic | llm_mcp_fallback | failed",
    )
    fallback_reason: Optional[str] = Field(
        None,
        description="Why deterministic path was skipped/failed",
    )
    caveats: Optional[str] = Field(None, description="Builder or LLM caveats")


# ---------------------------------------------------------------------------
# Legacy frontend contract (optional; not workflow final output this iteration)
# ---------------------------------------------------------------------------


class AnalyticsPoint(BaseModel):
    fromTime: str = Field(..., description="ISO-8601 window start (inclusive)")
    toTime: str = Field(..., description="ISO-8601 window end (exclusive or inclusive)")
    metricName: str = Field(..., description="Metric key, e.g. conversion_rate")
    metricValue: float = Field(..., description="Numeric metric value for this point")
    dimensionName: Optional[str] = Field(
        None,
        description='Optional slice key, e.g. "country" / "device_type"',
    )
    dimensionValue: Optional[str] = Field(
        None,
        description='Optional slice value, e.g. "IN" / "iOS"',
    )


class InsightData(BaseModel):
    metricNames: list[str] = Field(
        ...,
        description="Metric names present in points",
    )
    points: list[AnalyticsPoint] = Field(
        default_factory=list,
        description="Aggregated points only — never raw event rows",
    )


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(..., description="Narrative / caveat / SQL summary for the UI")


class InsightBlock(BaseModel):
    type: Literal["insight"] = "insight"
    title: Optional[str] = Field(None, description="Short chart / insight title")
    caption: Optional[str] = Field(None, description="Supporting sentence under the title")
    kind: Literal["timeseries", "breakdown", "comparison", "table", "funnel"] = Field(
        ...,
        description="Chart kind: timeseries | breakdown | comparison | table | funnel",
    )
    data: InsightData


AnalyticsBlock = Union[TextBlock, InsightBlock]


class AnalyticsResponse(BaseModel):
    """Frontend analytics payload — ordered blocks of text and/or insights."""

    blocks: list[AnalyticsBlock] = Field(
        ...,
        description="Ordered UI blocks; any mix of text and insight",
    )
