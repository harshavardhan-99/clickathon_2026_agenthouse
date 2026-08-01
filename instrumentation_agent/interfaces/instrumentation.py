"""Instrumentation interfaces used by instrument/registry routers and Agno tools."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.db.meta_events import MetaEventsCRUD
from instrumentation_agent.db.meta_features import MetaFeaturesCRUD
from instrumentation_agent.models.schemas import (
    EventSummary,
    InstrumentResponse,
    RegistryResponse,
)
from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import apply_event_table, get_client
from instrumentation_agent.utils.paths import resolve_feature_paths
from instrumentation_agent.utils.profiler import profile_feature


def get_registry(feature_id: str) -> RegistryResponse:
    features = MetaFeaturesCRUD()
    events = MetaEventsCRUD()
    return RegistryResponse(
        feature_id=feature_id,
        feature=features.get_by_feature_id(feature_id),
        events=events.list_by_feature_id(feature_id),
    )


def instrument_feature(
    feature_id: str | None = None,
    *,
    dataset_path: str | Path | None = None,
    spec_path: str | Path | None = None,
) -> InstrumentResponse:
    """Profile → ClickHouse (SQLGlot DDL) → Postgres metadata CRUD.

    Accepts either ``SPECS_ROOT/{feature_id}`` or an explicit dataset directory
    containing ``events.ndjson`` plus ``spec.md`` (or ``spec_path`` override).
    """
    paths = resolve_feature_paths(
        feature_id=feature_id,
        dataset_path=dataset_path,
        spec_path=spec_path,
    )
    paths.require_exists()
    run_id = uuid4()
    settings = get_settings()
    features = MetaFeaturesCRUD()
    events_crud = MetaEventsCRUD()

    try:
        profile = profile_feature(paths.feature_id, paths.spec_path, paths.events_path)
        client = get_client(settings)
        try:
            for event in profile.events:
                apply_event_table(event, client=client, settings=settings, recreate=True)
        finally:
            client.close()

        engine = get_engine()
        with engine.begin() as conn:
            features.upsert_ok(
                feature_id=paths.feature_id,
                run_id=run_id,
                spec_path=str(paths.spec_path),
                events_path=str(paths.events_path),
                events=profile.events,
                conn=conn,
            )
            events_crud.replace_for_feature(
                feature_id=paths.feature_id,
                run_id=run_id,
                events=profile.events,
                conn=conn,
            )

        return InstrumentResponse(
            status="ok",
            run_id=str(run_id),
            feature_id=paths.feature_id,
            events=[
                EventSummary(
                    event_name=e.event_name,
                    journey_order=e.journey_order,
                    ch_table=e.ch_table,
                    row_count=e.row_count,
                )
                for e in profile.events
            ],
        )
    except Exception as exc:  # noqa: BLE001
        try:
            features.upsert_failed(
                feature_id=paths.feature_id,
                run_id=run_id,
                spec_path=str(paths.spec_path),
                events_path=str(paths.events_path),
                error=str(exc),
            )
        except Exception:  # noqa: BLE001
            pass
        raise
