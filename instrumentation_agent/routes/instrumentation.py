"""Instrumentation REST routes — thin wrappers over interfaces.instrumentation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from instrumentation_agent.interfaces.instrumentation import get_registry, instrument_feature
from instrumentation_agent.models.schemas import (
    InstrumentRequest,
    InstrumentResponse,
    RegistryResponse,
)

router = APIRouter(tags=["instrumentation"])


@router.get("/v1/registry/{feature_id}", response_model=RegistryResponse)
def read_registry(feature_id: str) -> RegistryResponse:
    try:
        return get_registry(feature_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"registry unavailable: {exc}") from exc


@router.post("/v1/instrument", response_model=InstrumentResponse)
def instrument(body: InstrumentRequest) -> InstrumentResponse:
    try:
        return instrument_feature(body.feature_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"instrumentation failed: {exc}") from exc
