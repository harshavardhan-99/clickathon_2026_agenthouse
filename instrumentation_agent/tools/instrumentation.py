"""Agno Toolkit for instrumentation (profile → CH → Postgres registry)."""

from __future__ import annotations

import json
from typing import Any

from agno.tools import Toolkit

from instrumentation_agent.utils.pipeline import run_instrumentation
from instrumentation_agent.utils.registry import get_feature_registry


class InstrumentationTools(Toolkit):
    """Tools the Instrumentation Agno agent can call."""

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.instrument_feature,
            self.get_registry,
        ]
        super().__init__(name="instrumentation_tools", tools=tools, **kwargs)

    def instrument_feature(self, feature_id: str) -> str:
        """Onboard a feature: create ClickHouse tables, load events, upsert Postgres metadata.

        Args:
            feature_id: Spec folder name under SPECS_ROOT (e.g. 01_express_checkout).
        """
        result = run_instrumentation(feature_id)
        return json.dumps(result)

    def get_registry(self, feature_id: str) -> str:
        """Return Postgres meta_features + meta_events for a feature_id.

        Args:
            feature_id: Feature id previously instrumented.
        """
        return json.dumps(get_feature_registry(feature_id))
