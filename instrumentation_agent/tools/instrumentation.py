"""Agno Toolkit for instrumentation — delegates to interfaces."""

from __future__ import annotations

from typing import Any

from agno.tools import Toolkit

from instrumentation_agent.interfaces.instrumentation import get_registry, instrument_feature


class InstrumentationTools(Toolkit):
    """Tools the Instrumentation Agno agent can call."""

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.instrument_feature,
            self.get_registry,
        ]
        super().__init__(name="instrumentation_tools", tools=tools, **kwargs)

    def instrument_feature(self, feature_id: str) -> str:
        """Onboard a feature: ClickHouse tables + Postgres metadata.

        Args:
            feature_id: Spec folder name under SPECS_ROOT (e.g. 01_express_checkout).
        """
        return instrument_feature(feature_id).model_dump_json()

    def get_registry(self, feature_id: str) -> str:
        """Return Postgres meta_features + meta_events for a feature_id.

        Args:
            feature_id: Feature id previously instrumented.
        """
        return get_registry(feature_id).model_dump_json()
