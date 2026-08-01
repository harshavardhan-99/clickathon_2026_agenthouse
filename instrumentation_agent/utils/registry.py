"""Persist / read meta_features (journey) + meta_events (event-level)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, Row, text

from instrumentation_agent.models import EventProfile
from instrumentation_agent.utils.postgres import get_engine


def _row_to_dict(row: Row[Any]) -> dict[str, Any]:
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, UUID):
            data[key] = str(value)
    return data


def _journey_payload(events: list[EventProfile]) -> list[dict[str, Any]]:
    return [
        {
            "event_name": e.event_name,
            "journey_order": e.journey_order,
            "ch_table": e.ch_table,
            "row_count": e.row_count,
        }
        for e in events
    ]


def upsert_feature_metadata(
    *,
    feature_id: str,
    run_id: UUID,
    status: str,
    spec_path: str,
    events_path: str,
    events: list[EventProfile],
    error: str | None = None,
    engine: Engine | None = None,
) -> None:
    """Upsert feature journey row + replace event-level rows for the feature."""
    eng = engine or get_engine()
    journey = _journey_payload(events)
    event_count = sum(e.row_count for e in events)
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO meta_features
                  (feature_id, journey, status, spec_path, events_path,
                   run_id, event_count, error, updated_at)
                VALUES
                  (:feature_id, CAST(:journey AS jsonb), :status, :spec_path, :events_path,
                   :run_id, :event_count, :error, now())
                ON CONFLICT (feature_id) DO UPDATE SET
                  journey = EXCLUDED.journey,
                  status = EXCLUDED.status,
                  spec_path = EXCLUDED.spec_path,
                  events_path = EXCLUDED.events_path,
                  run_id = EXCLUDED.run_id,
                  event_count = EXCLUDED.event_count,
                  error = EXCLUDED.error,
                  updated_at = now()
                """
            ),
            {
                "feature_id": feature_id,
                "journey": json.dumps(journey),
                "status": status,
                "spec_path": spec_path,
                "events_path": events_path,
                "run_id": run_id,
                "event_count": event_count,
                "error": error,
            },
        )

        conn.execute(
            text("DELETE FROM meta_events WHERE feature_id = :feature_id"),
            {"feature_id": feature_id},
        )
        for ev in events:
            conn.execute(
                text(
                    """
                    INSERT INTO meta_events
                      (event_name, feature_id, journey_order, ch_table,
                       row_count, run_id, columns)
                    VALUES
                      (:event_name, :feature_id, :journey_order, :ch_table,
                       :row_count, :run_id, CAST(:columns AS jsonb))
                    """
                ),
                {
                    "event_name": ev.event_name,
                    "feature_id": feature_id,
                    "journey_order": ev.journey_order,
                    "ch_table": ev.ch_table,
                    "row_count": ev.row_count,
                    "run_id": run_id,
                    "columns": json.dumps(ev.columns),
                },
            )


def record_failed_feature(
    *,
    feature_id: str,
    run_id: UUID,
    spec_path: str,
    events_path: str,
    error: str,
    engine: Engine | None = None,
) -> None:
    eng = engine or get_engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO meta_features
                  (feature_id, journey, status, spec_path, events_path,
                   run_id, event_count, error, updated_at)
                VALUES
                  (:feature_id, '[]'::jsonb, 'failed', :spec_path, :events_path,
                   :run_id, 0, :error, now())
                ON CONFLICT (feature_id) DO UPDATE SET
                  status = 'failed',
                  spec_path = EXCLUDED.spec_path,
                  events_path = EXCLUDED.events_path,
                  run_id = EXCLUDED.run_id,
                  error = EXCLUDED.error,
                  updated_at = now()
                """
            ),
            {
                "feature_id": feature_id,
                "spec_path": spec_path,
                "events_path": events_path,
                "run_id": run_id,
                "error": error,
            },
        )


def get_feature_registry(
    feature_id: str,
    *,
    engine: Engine | None = None,
) -> dict[str, Any]:
    eng = engine or get_engine()
    with eng.connect() as conn:
        feature = conn.execute(
            text(
                """
                SELECT feature_id, journey, status, spec_path, events_path,
                       run_id, event_count, error, updated_at
                FROM meta_features
                WHERE feature_id = :feature_id
                """
            ),
            {"feature_id": feature_id},
        ).first()

        events = conn.execute(
            text(
                """
                SELECT event_name, feature_id, journey_order, ch_table,
                       row_count, run_id, columns, registered_at
                FROM meta_events
                WHERE feature_id = :feature_id
                ORDER BY journey_order
                """
            ),
            {"feature_id": feature_id},
        ).all()

    return {
        "feature_id": feature_id,
        "feature": _row_to_dict(feature) if feature else None,
        "events": [_row_to_dict(r) for r in events],
    }
