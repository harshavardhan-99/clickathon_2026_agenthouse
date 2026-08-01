"""Resolve feature ``spec.md`` / ``events.ndjson`` paths."""

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


def resolve_feature_paths(
    *,
    feature_id: str | None = None,
    dataset_path: str | Path | None = None,
    spec_path: str | Path | None = None,
    settings: Settings | None = None,
) -> FeaturePaths:
    """Resolve paths for a feature pack.

    - If ``dataset_path`` is set: that directory holds ``events.ndjson`` (and
      ``spec.md`` unless ``spec_path`` overrides).
    - Else: ``SPECS_ROOT/{feature_id}/``.
    """
    if dataset_path is not None:
        feature_dir = Path(dataset_path).expanduser().resolve()
        fid = feature_id or feature_dir.name
        events = feature_dir / "events.ndjson"
        spec = (
            Path(spec_path).expanduser().resolve()
            if spec_path is not None
            else feature_dir / "spec.md"
        )
        return FeaturePaths(
            feature_id=fid,
            feature_dir=feature_dir,
            spec_path=spec,
            events_path=events,
        )

    if not feature_id:
        raise ValueError("feature_id is required when dataset_path is not provided")
    return feature_paths(feature_id, settings=settings)
