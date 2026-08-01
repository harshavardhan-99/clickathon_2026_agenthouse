"""CRUD for ``meta_features``."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, Connection, text

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.utils.serialize import row_to_dict


class MetaFeaturesCRUD:
    """Create / read / update rows in ``meta_features``."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def upsert_ok(
        self,
        *,
        feature_id: str,
        run_id: UUID,
        spec_path: str,
        events_path: str,
        events: list[EventProfile],
        conn: Connection | None = None,
    ) -> None:
        journey = [
            {
                "event_name": e.event_name,
                "journey_order": e.journey_order,
                "ch_table": e.ch_table,
                "row_count": e.row_count,
            }
            for e in events
        ]
        params = {
            "feature_id": feature_id,
            "journey": json.dumps(journey),
            "status": "ok",
            "spec_path": spec_path,
            "events_path": events_path,
            "run_id": run_id,
            "event_count": sum(e.row_count for e in events),
            "error": None,
        }
        self._upsert(params, conn=conn)

    def upsert_failed(
        self,
        *,
        feature_id: str,
        run_id: UUID,
        spec_path: str,
        events_path: str,
        error: str,
        conn: Connection | None = None,
    ) -> None:
        params = {
            "feature_id": feature_id,
            "journey": "[]",
            "status": "failed",
            "spec_path": spec_path,
            "events_path": events_path,
            "run_id": run_id,
            "event_count": 0,
            "error": error,
        }
        self._upsert(params, conn=conn)

    def _upsert(self, params: dict[str, Any], *, conn: Connection | None) -> None:
        sql = text(
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
        )
        if conn is not None:
            conn.execute(sql, params)
            return
        with self._engine.begin() as opened:
            opened.execute(sql, params)

    def get_by_feature_id(self, feature_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
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
        return row_to_dict(row) if row else None
