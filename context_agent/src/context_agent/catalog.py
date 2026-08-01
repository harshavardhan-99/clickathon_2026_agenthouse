"""Deterministic catalog queries for Context Agent tools."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from context_agent.db import get_registry_engine


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row._mapping)
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
    """Return meta objects, events (funnel order), and fields for one feature."""
    if not feature_id or not feature_id.strip():
        return {"error": "feature_id is required"}

    feature_id = feature_id.strip()
    engine = get_registry_engine()
    with engine.connect() as conn:
        objects = conn.execute(
            text(
                """
                SELECT name, feature_id, kind, engine, order_by, partition_by,
                       source, target, purpose, created_at, updated_at
                FROM meta_objects
                WHERE feature_id = :feature_id
                ORDER BY kind, name
                """
            ),
            {"feature_id": feature_id},
        ).mappings().all()

        events = conn.execute(
            text(
                """
                SELECT feature_id, event_name, object_name, funnel_stage,
                       sample_count, created_at, updated_at
                FROM meta_events
                WHERE feature_id = :feature_id
                ORDER BY funnel_stage, event_name
                """
            ),
            {"feature_id": feature_id},
        ).mappings().all()

        fields = conn.execute(
            text(
                """
                SELECT feature_id, event_name, field_path, column_name,
                       inferred_type, null_rate, example_values,
                       created_at, updated_at
                FROM meta_fields
                WHERE feature_id = :feature_id
                ORDER BY event_name, field_path
                """
            ),
            {"feature_id": feature_id},
        ).mappings().all()

        field_rows = []
        for r in fields:
            item = _row_to_dict(r)
            ev = item.get("example_values")
            if isinstance(ev, str):
                try:
                    item["example_values"] = json.loads(ev)
                except json.JSONDecodeError:
                    pass
            field_rows.append(item)

        return {
            "feature_id": feature_id,
            "objects": [_row_to_dict(r) for r in objects],
            "events": [_row_to_dict(r) for r in events],
            "fields": field_rows,
        }
