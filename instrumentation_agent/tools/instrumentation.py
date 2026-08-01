"""Agno Toolkit for instrumentation — delegates to interfaces."""

from __future__ import annotations

from typing import Any

from agno.tools import Toolkit

from instrumentation_agent.interfaces.instrumentation import get_registry, instrument_feature


class InstrumentationTools(Toolkit):
    """Tools the Instrumentation Agno agent can call."""

    def __init__(self, **kwargs: Any) -> None:
        tools = [
            self.instrument_dataset,
            self.get_registry,
        ]
        super().__init__(name="instrumentation_tools", tools=tools, **kwargs)

    def instrument_dataset(
        self,
        feature_id: str = "",
        dataset_path: str = "",
        spec_path: str = "",
    ) -> str:
        """Instrument a feature pack: spec.md + events.ndjson → ClickHouse + Postgres.

        Prefer evidence from NDJSON (do not invent columns). One table per event,
        ORDER BY time+segment keys, PARTITION BY month on timestamp.

        Args:
            feature_id: Feature id (defaults to dataset folder name when empty).
            dataset_path: Directory with events.ndjson (and spec.md unless spec_path set).
                Empty string means use SPECS_ROOT/{feature_id}/.
            spec_path: Optional explicit path to spec.md.
        """
        return instrument_feature(
            feature_id or None,
            dataset_path=dataset_path or None,
            spec_path=spec_path or None,
        ).model_dump_json()

    def get_registry(self, feature_id: str) -> str:
        """Return Postgres meta_features + meta_events for a feature_id.

        Args:
            feature_id: Feature id previously instrumented.
        """
        return get_registry(feature_id).model_dump_json()
