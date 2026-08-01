"""Deterministic instrumentation: profile → ClickHouse → Postgres registry."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from instrumentation_agent.settings import get_settings
from instrumentation_agent.utils.clickhouse import apply_event_table, get_client
from instrumentation_agent.utils.paths import feature_paths
from instrumentation_agent.utils.profiler import profile_feature
from instrumentation_agent.utils.registry import record_failed_feature, upsert_feature_metadata


def run_instrumentation(feature_id: str) -> dict[str, Any]:
    """Onboard a feature: create CH tables, load NDJSON, record Postgres metadata."""
    paths = feature_paths(feature_id)
    paths.require_exists()
    run_id = uuid4()
    settings = get_settings()

    try:
        profile = profile_feature(feature_id, paths.spec_path, paths.events_path)
        client = get_client(settings)
        try:
            for event in profile.events:
                apply_event_table(event, client=client, settings=settings, recreate=True)
        finally:
            client.close()

        upsert_feature_metadata(
            feature_id=feature_id,
            run_id=run_id,
            status="ok",
            spec_path=str(paths.spec_path),
            events_path=str(paths.events_path),
            events=profile.events,
        )

        return {
            "status": "ok",
            "run_id": str(run_id),
            "feature_id": feature_id,
            "events": [
                {
                    "event_name": e.event_name,
                    "journey_order": e.journey_order,
                    "ch_table": e.ch_table,
                    "row_count": e.row_count,
                }
                for e in profile.events
            ],
        }
    except Exception as exc:  # noqa: BLE001
        try:
            record_failed_feature(
                feature_id=feature_id,
                run_id=run_id,
                spec_path=str(paths.spec_path),
                events_path=str(paths.events_path),
                error=str(exc),
            )
        except Exception:  # noqa: BLE001
            pass
        raise
