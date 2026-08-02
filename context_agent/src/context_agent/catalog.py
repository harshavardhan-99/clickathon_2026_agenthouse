"""Deterministic catalog queries for Context Agent tools."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from context_agent.db import get_registry_engine


def _row_to_dict(row: Any) -> dict[str, Any]:
    # RowMapping from .mappings() has no usable ._mapping; Row does.
    mapping = getattr(row, "_mapping", None)
    d = dict(mapping) if mapping is not None else dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def get_latest_context_items(kinds: list[str] | None = None) -> dict[str, Any]:
    """Return current context_version and its context_items.

    Optional kinds filter: entity | metric | join | funnel_step | issue | contradiction.
    """
    engine = get_registry_engine()
    with engine.connect() as conn:
        ver = conn.execute(
            text(
                """
                SELECT context_version, parent_version, source, feature_id, summary,
                       created_at, updated_at
                FROM context_versions
                WHERE is_current = true
                LIMIT 1
                """
            )
        ).mappings().first()

        if ver is None:
            return {
                "context_version": None,
                "version": None,
                "items": [],
                "message": "No current context_version (is_current=true) found.",
            }

        version = ver["context_version"]
        if kinds:
            placeholders = ", ".join(f":kind_{i}" for i in range(len(kinds)))
            params: dict[str, Any] = {"version": version}
            params.update({f"kind_{i}": k for i, k in enumerate(kinds)})
            rows = conn.execute(
                text(
                    f"""
                    SELECT kind, item_key, label, payload, created_at, updated_at
                    FROM context_items
                    WHERE context_version = :version
                      AND kind IN ({placeholders})
                    ORDER BY kind, item_key
                    """
                ),
                params,
            ).mappings().all()
        else:
            rows = conn.execute(
                text(
                    """
                    SELECT kind, item_key, label, payload, created_at, updated_at
                    FROM context_items
                    WHERE context_version = :version
                    ORDER BY kind, item_key
                    """
                ),
                {"version": version},
            ).mappings().all()

        items = []
        for r in rows:
            item = _row_to_dict(r)
            payload = item.get("payload")
            if isinstance(payload, str):
                try:
                    item["payload"] = json.loads(payload)
                except json.JSONDecodeError:
                    pass
            items.append(item)

        return {
            "context_version": version,
            "version": _row_to_dict(ver),
            "items": items,
        }


def get_feature_meta(feature_id: str) -> dict[str, Any]:
    """Return Instrumentation meta for one feature (meta_features + meta_events).

    Reads tables owned by instrumentation_agent — see TABLES.md.
    """
    if not feature_id or not feature_id.strip():
        return {"error": "feature_id is required"}

    feature_id = feature_id.strip()
    engine = get_registry_engine()
    with engine.connect() as conn:
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
        ).mappings().first()

        events = conn.execute(
            text(
                """
                SELECT event_name, feature_id, journey_order, ch_table,
                       row_count, run_id, columns, registered_at
                FROM meta_events
                WHERE feature_id = :feature_id
                ORDER BY journey_order, event_name
                """
            ),
            {"feature_id": feature_id},
        ).mappings().all()

        feature_row: dict[str, Any] | None = None
        if feature is not None:
            feature_row = _row_to_dict(feature)
            journey = feature_row.get("journey")
            if isinstance(journey, str):
                try:
                    feature_row["journey"] = json.loads(journey)
                except json.JSONDecodeError:
                    pass

        event_rows = []
        for r in events:
            item = _row_to_dict(r)
            cols = item.get("columns")
            if isinstance(cols, str):
                try:
                    item["columns"] = json.loads(cols)
                except json.JSONDecodeError:
                    pass
            event_rows.append(item)

        if feature_row is None and not event_rows:
            return {
                "feature_id": feature_id,
                "feature": None,
                "events": [],
                "message": "No meta_features / meta_events for this feature_id.",
            }

        return {
            "feature_id": feature_id,
            "feature": feature_row,
            "events": event_rows,
        }
