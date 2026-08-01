"""Instrumentation REST routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from instrumentation_agent.interfaces import InstrumentRequest, InstrumentResponse, RegistryResponse
from instrumentation_agent.utils.pipeline import run_instrumentation
from instrumentation_agent.utils.registry import get_feature_registry

router = APIRouter(tags=["instrumentation"])


@router.get("/v1/registry/{feature_id}", response_model=RegistryResponse)
def read_registry(feature_id: str) -> RegistryResponse:
    try:
        payload = get_feature_registry(feature_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"registry unavailable: {exc}") from exc
    return RegistryResponse(**payload)


@router.post("/v1/instrument", response_model=InstrumentResponse)
def instrument(body: InstrumentRequest) -> InstrumentResponse:
    try:
        payload = run_instrumentation(body.feature_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"instrumentation failed: {exc}") from exc
    return InstrumentResponse(**payload)
