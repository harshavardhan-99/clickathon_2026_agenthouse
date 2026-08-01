"""Health / connectivity routes."""

from __future__ import annotations

from fastapi import APIRouter

from instrumentation_agent.interfaces import HealthResponse
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import ping_clickhouse
from instrumentation_agent.utils.postgres import ping_postgres

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    status = "ok"
    try:
        ping_postgres()
        postgres = "up"
    except Exception as exc:  # noqa: BLE001
        postgres = f"down: {exc}"
        status = "degraded"
    try:
        ping_clickhouse()
        clickhouse = "up"
    except Exception as exc:  # noqa: BLE001
        clickhouse = f"down: {exc}"
        status = "degraded"
    return HealthResponse(
        status=status,
        postgres=postgres,
        clickhouse=clickhouse,
        specs_root=str(settings.specs_root),
    )
