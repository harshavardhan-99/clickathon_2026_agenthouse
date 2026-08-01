"""Use-case toolkit: two deterministic Postgres catalog tools."""

from __future__ import annotations

import json
from typing import Optional, Sequence

from agno.tools import Toolkit

from context_agent.catalog import get_feature_meta, get_latest_context_items


class ContextCatalogTools(Toolkit):
    """Fat, deterministic tools for Conversation / operators (not free-form SQL)."""

    def __init__(self):
        tools = [
            self.get_latest_context_items,
            self.get_feature_meta,
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
        """Load meta for one feature: objects, events (funnel order), and fields.

        Use for feature-specific PM questions (Express, Group, Forex, …).
        Events are ordered by funnel_stage. Fields include column names for CH SQL.

        Args:
            feature_id: e.g. \"01_express_checkout\"
        """
        result = get_feature_meta(feature_id=feature_id)
        return json.dumps(result, default=str)


def get_context_catalog_tools() -> ContextCatalogTools:
    """Factory for other agents: two tools, no free-form SQL."""
    return ContextCatalogTools()
