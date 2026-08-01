"""CRUD for ``meta_events``."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from instrumentation_agent.db.connection import get_engine
from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.utils.serialize import row_to_dict


class MetaEventsCRUD:
    """Create / read / delete rows in ``meta_events``."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def replace_for_feature(
        self,
        *,
        feature_id: str,
        run_id: UUID,
        events: list[EventProfile],
        conn: Connection | None = None,
    ) -> None:
        def _write(c: Connection) -> None:
            c.execute(
                text("DELETE FROM meta_events WHERE feature_id = :feature_id"),
                {"feature_id": feature_id},
            )
            insert = text(
                """
                INSERT INTO meta_events
                  (event_name, feature_id, journey_order, ch_table,
                   row_count, run_id, columns)
                VALUES
                  (:event_name, :feature_id, :journey_order, :ch_table,
                   :row_count, :run_id, CAST(:columns AS jsonb))
                """
            )
            for ev in events:
                c.execute(
                    insert,
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

        if conn is not None:
            _write(conn)
            return
        with self._engine.begin() as opened:
            _write(opened)

    def list_by_feature_id(self, feature_id: str) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
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
        return [row_to_dict(r) for r in rows]
