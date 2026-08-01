"""Resolve feature ``spec.md`` / ``events.ndjson`` under ``SPECS_ROOT``."""

from __future__ import annotations

from pathlib import Path

from instrumentation_agent.models.domain import FeaturePaths
from instrumentation_agent.settings import Settings, get_settings


def feature_paths(feature_id: str, *, settings: Settings | None = None) -> FeaturePaths:
    """``SPECS_ROOT/{feature_id}/spec.md`` and ``events.ndjson``."""
    cfg = settings or get_settings()
    feature_dir = Path(cfg.specs_root).expanduser().resolve() / feature_id
    return FeaturePaths(
        feature_id=feature_id,
        feature_dir=feature_dir,
        spec_path=feature_dir / "spec.md",
        events_path=feature_dir / "events.ndjson",
    )
