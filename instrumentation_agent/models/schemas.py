"""Pydantic request / response schemas for API routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InstrumentRequest(BaseModel):
    feature_id: str = Field(..., examples=["01_express_checkout"])


class EventSummary(BaseModel):
    event_name: str
    journey_order: int
    ch_table: str
    row_count: int


class InstrumentResponse(BaseModel):
    status: str
    run_id: str
    feature_id: str
    events: list[EventSummary]


class HealthResponse(BaseModel):
    status: str
    postgres: str
    clickhouse: str
    specs_root: str


class RegistryResponse(BaseModel):
    feature_id: str
    feature: dict[str, Any] | None
    events: list[dict[str, Any]]
