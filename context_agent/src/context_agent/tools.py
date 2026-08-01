"""Use-case toolkit: read catalog + publish context version."""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from agno.tools import Toolkit

import context_agent.catalog as _catalog
from context_agent.catalog import get_feature_meta, get_latest_context_items
from context_agent.publish import publish_context_version


def _row_to_dict_compatible(row: Any) -> dict[str, Any]:
    """RowMapping (.mappings()) has no usable ._mapping attr — use dict(row)."""
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# catalog._row_to_dict breaks on SQLAlchemy RowMapping; patch without editing catalog.py
_catalog._row_to_dict = _row_to_dict_compatible


class ContextCatalogTools(Toolkit):
    """Deterministic tools for Conversation / operators (not free-form SQL)."""

    def __init__(self):
        tools = [
            self.get_latest_context_items,
            self.get_feature_meta,
            self.publish_context_version,
        ]
        super().__init__(name="context_catalog", tools=tools)

    def get_latest_context_items(self, kinds: Optional[str] = None) -> str:
        """Load the current living context (version + items).

        Call this first for any analytics question. Returns context_version and
        context_items (entities, metrics, joins, core funnel_steps, issues,
        contradictions).

        Args:
            kinds: Optional comma-separated kinds to filter, e.g.
                   \"metric,issue,funnel_step\". Omit for all kinds.
        """
        kind_list: Sequence[str] | None = None
        if kinds and kinds.strip():
            kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
        result = get_latest_context_items(kinds=list(kind_list) if kind_list else None)
        return json.dumps(result, default=str)

    def get_feature_meta(self, feature_id: str) -> str:
        """Load Instrumentation meta for one feature (meta_features + meta_events).

        Use for feature-specific PM questions (Express, Group, Forex, …).
        Events are ordered by journey_order; column shapes are in events.columns.

        Args:
            feature_id: e.g. \"01_express_checkout\"
        """
        result = get_feature_meta(feature_id=feature_id)
        return json.dumps(result, default=str)

    def publish_context_version(
        self,
        context_version: str,
        source: str,
        summary: Optional[str] = None,
        feature_id: Optional[str] = None,
        parent_version: Optional[str] = None,
        upserts_json: Optional[str] = None,
        deletes_json: Optional[str] = None,
        copy_forward: bool = True,
    ) -> str:
        """Publish a new context version (copy-forward parent items + deltas).

        Use for seed or after Instrumentation reconcile. Does not write meta_*.

        Args:
            context_version: New version id, e.g. \"v1\" or \"v3\".
            source: e.g. \"seed\", \"instrumentation\", \"manual\".
            summary: Short human summary of what changed.
            feature_id: Optional feature that triggered this publish.
            parent_version: Parent to copy from; omit to use current is_current.
            upserts_json: JSON array of
                {\"kind\",\"item_key\",\"label?\",\"payload?\"}.
                kind: entity|metric|join|funnel_step|issue|contradiction.
            deletes_json: JSON array of {\"kind\",\"item_key\"} removed after copy.
            copy_forward: If true (default), copy all parent items first.
        """
        try:
            upserts = json.loads(upserts_json) if upserts_json else []
            deletes = json.loads(deletes_json) if deletes_json else []
            if not isinstance(upserts, list) or not isinstance(deletes, list):
                return json.dumps(
                    {"error": "upserts_json and deletes_json must be JSON arrays"}
                )
            result = publish_context_version(
                context_version=context_version,
                source=source,
                summary=summary,
                feature_id=feature_id,
                parent_version=parent_version,
                upserts=upserts,
                deletes=deletes,
                copy_forward=copy_forward,
            )
            return json.dumps(result, default=str)
        except (ValueError, json.JSONDecodeError) as exc:
            return json.dumps({"error": str(exc)})


def get_context_catalog_tools() -> ContextCatalogTools:
    """Factory for other agents: read tools + publish_context_version."""
    return ContextCatalogTools()
