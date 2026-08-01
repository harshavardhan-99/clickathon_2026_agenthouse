"""Domain models for instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EventProfile:
    event_name: str
    journey_order: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: dict[str, str] = field(default_factory=dict)  # col -> CH type

    @property
    def ch_table(self) -> str:
        return self.event_name

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass
class FeatureProfile:
    feature_id: str
    events: list[EventProfile]


@dataclass(frozen=True)
class FeaturePaths:
    feature_id: str
    feature_dir: Path
    spec_path: Path
    events_path: Path

    def require_exists(self) -> None:
        missing = [p for p in (self.spec_path, self.events_path) if not p.is_file()]
        if missing:
            names = ", ".join(str(p) for p in missing)
            raise FileNotFoundError(f"feature inputs missing: {names}")
