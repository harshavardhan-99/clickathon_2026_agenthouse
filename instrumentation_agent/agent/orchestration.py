"""Instrumentation Agno Workflow — invoked by POST /v1/instrument.

See https://docs.agno.com/workflows/overview

Steps:
1. Load ``spec.md`` (+ path context) as a **string** prompt for the next agent.
2. Summarize the spec into structured event / feature metadata JSON.
3. Use that metadata + mocked pipeline tools to decide create / update / skip.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from agno.agent import Agent
from agno.models.google import Gemini
from agno.workflow import Step, StepInput, StepOutput, Workflow

from instrumentation_agent.models.schemas import (
    EventSummary,
    FeatureSpecMetadata,
    InstrumentRequest,
    InstrumentResponse,
    PipelinePlan,
)
from instrumentation_agent.settings import get_settings
from instrumentation_agent.tools.pipeline import PipelineTools
from instrumentation_agent.utils.paths import resolve_feature_paths

_SUMMARIZE_INSTRUCTIONS = """\
You are the Spec Metadata agent for Atlys AgentHouse (Click-a-thon).

You receive the feature pack context including the full `spec.md` text.
Produce structured JSON metadata for the feature and each journey event.

Rules:
- Use ONLY events listed in the spec journey / user-actions bullets.
- Preserve journey order (1-based).
- Set ch_table to the event_name unless the spec explicitly says otherwise.
- Do NOT invent columns that are not hinted by the spec; expected_columns may be empty.
- Always include the shared join envelope in join_keys when present in contest guidance:
  user_id, application_id, device_type, os, geoip_country_code, destination, timestamp.
- feature_id must match the provided feature_id.
"""

_PIPELINE_INSTRUCTIONS = """\
You are the Pipeline Planner for Atlys AgentHouse (Click-a-thon).

You receive structured FeatureSpecMetadata JSON from the previous step.
Decide whether to build a new pipeline, update an existing one, or skip.

You MUST call exactly one of these mocked tools after inspecting state:
1. inspect_existing_pipeline(feature_id) — always call this first.
2. Then choose ONE of: create_pipeline | update_pipeline | skip_pipeline.

When calling create/update, pass the event names from the metadata journey.
After tools return, output a PipelinePlan JSON matching the schema.
The tools are mocked stubs for now — treat their JSON responses as authoritative.
"""


def _ensure_google_api_key() -> None:
    settings = get_settings()
    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key


def _gemini() -> Gemini:
    settings = get_settings()
    return Gemini(id=settings.gemini_model, api_key=settings.google_api_key or None)


def load_spec_inputs(step_input: StepInput) -> StepOutput:
    """Resolve dataset/spec paths and load ``spec.md`` for the summarizer.

    Important: Agno agent steps treat dict inputs as ``Message`` objects (require
    ``role``). Always return a **string** so Gemini receives valid contents.
    """
    payload = _as_dict(step_input.input)
    extra = step_input.additional_data or {}
    feature_id = payload.get("feature_id") or extra.get("feature_id")
    dataset_path = payload.get("dataset_path") or extra.get("dataset_path")
    spec_path = payload.get("spec_path") or extra.get("spec_path")

    paths = resolve_feature_paths(
        feature_id=feature_id,
        dataset_path=dataset_path,
        spec_path=spec_path,
    )
    paths.require_exists()
    spec_text = paths.spec_path.read_text(encoding="utf-8")

    # Plain text prompt — do NOT return a dict (breaks Gemini Message validation).
    prompt = (
        f"Summarize this feature pack into FeatureSpecMetadata JSON.\n\n"
        f"feature_id: {paths.feature_id}\n"
        f"dataset_path: {paths.feature_dir}\n"
        f"spec_path: {paths.spec_path}\n"
        f"events_path: {paths.events_path}\n\n"
        f"=== spec.md ===\n{spec_text}\n"
    )

    print("START prompt")
    print("prompt", prompt)
    print("END prompt")
    
    return StepOutput(content=prompt)


@lru_cache
def get_instrumentation_workflow() -> Workflow:
    """Build the Instrumentation workflow (cached)."""
    _ensure_google_api_key()

    summarize_agent = Agent(
        name="SpecMetadata",
        model=_gemini(),
        instructions=_SUMMARIZE_INSTRUCTIONS,
        output_schema=FeatureSpecMetadata,
        markdown=False,
    )
    pipeline_agent = Agent(
        name="PipelinePlanner",
        model=_gemini(),
        tools=[PipelineTools()],
        instructions=_PIPELINE_INSTRUCTIONS,
        output_schema=PipelinePlan,
        markdown=False,
    )

    return Workflow(
        name="Instrumentation",
        description=(
            "Summarize spec.md into event metadata JSON, then decide "
            "create/update/skip pipeline via mocked tools."
        ),
        steps=[
            Step(name="load_spec", executor=load_spec_inputs),
            Step(name="summarize_spec", agent=summarize_agent, on_error="fail"),
            Step(name="plan_pipeline", agent=pipeline_agent, on_error="fail"),
        ],
    )


def run_instrumentation_agent(request: InstrumentRequest) -> InstrumentResponse:
    """Run the Instrumentation workflow for a dataset path + spec.md (or feature_id)."""
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Add a Gemini API key from "
            "https://aistudio.google.com/apikey to .env"
        )

    get_instrumentation_workflow.cache_clear()
    workflow = get_instrumentation_workflow()

    # String input only — dict payloads are mis-validated as Message(role=...).
    run = workflow.run(
        input=(
            "Load the feature pack, summarize spec.md into FeatureSpecMetadata, "
            "then plan the instrumentation pipeline with the mocked tools."
        ),
        additional_data={
            "feature_id": request.feature_id,
            "dataset_path": request.dataset_path,
            "spec_path": request.spec_path,
        },
    )
    return _response_from_workflow(run, request)


def _response_from_workflow(
    run: object,
    request: InstrumentRequest,
) -> InstrumentResponse:
    status = getattr(getattr(run, "status", None), "value", None) or str(
        getattr(run, "status", "") or ""
    )
    if status and status.lower() in {"error", "failed", "cancelled"}:
        content = getattr(run, "content", None) or status
        raise RuntimeError(f"Instrumentation workflow failed ({status}): {content}")

    run_id = getattr(run, "run_id", None) or str(uuid4())
    step_results = list(getattr(run, "step_results", None) or [])
    for step in step_results:
        if getattr(step, "success", True) is False:
            name = getattr(step, "step_name", "step")
            err = getattr(step, "error", None) or getattr(step, "content", None)
            raise RuntimeError(f"Workflow step '{name}' failed: {err}")

    by_name = {
        getattr(step, "step_name", None): getattr(step, "content", None)
        for step in step_results
        if getattr(step, "step_name", None)
    }

    load_text = by_name.get("load_spec")
    feature_id = request.feature_id
    if isinstance(load_text, str) and "feature_id:" in load_text:
        for line in load_text.splitlines():
            if line.startswith("feature_id:"):
                feature_id = line.split(":", 1)[1].strip() or feature_id
                break
    if not feature_id and request.dataset_path:
        feature_id = Path(request.dataset_path).name
    feature_id = feature_id or "unknown"

    spec_metadata = _parse_model(by_name.get("summarize_spec"), FeatureSpecMetadata)
    if spec_metadata is None:
        spec_metadata = _parse_model(getattr(run, "content", None), FeatureSpecMetadata)

    pipeline_plan = _parse_model(by_name.get("plan_pipeline"), PipelinePlan)
    if pipeline_plan is None:
        pipeline_plan = _parse_model(getattr(run, "content", None), PipelinePlan)

    if spec_metadata is None:
        raise RuntimeError(
            "summarize_spec produced no FeatureSpecMetadata. "
            "Check GOOGLE_API_KEY (Gemini Developer API). "
            "Keys starting with 'AQ.' often return 401 ACCESS_TOKEN_TYPE_UNSUPPORTED — "
            "create/regenerate a key at https://aistudio.google.com/apikey."
        )

    events = [
        EventSummary(
            event_name=e.event_name,
            journey_order=e.journey_order,
            ch_table=e.ch_table,
            row_count=0,
        )
        for e in spec_metadata.journey
    ]

    response_status = "planned"
    if pipeline_plan is not None:
        response_status = pipeline_plan.action

    return InstrumentResponse(
        status=response_status,
        run_id=str(run_id),
        feature_id=feature_id,
        events=events,
        agent_run_id=str(run_id),
        spec_metadata=spec_metadata,
        pipeline_plan=pipeline_plan,
    )


def _as_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[no-any-return]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_model(value: object, model_cls: type) -> Any | None:
    if value is None:
        return None
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        try:
            return model_cls.model_validate(value)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(value, str):
        try:
            return model_cls.model_validate_json(value)
        except Exception:  # noqa: BLE001
            try:
                return model_cls.model_validate(json.loads(value))
            except Exception:  # noqa: BLE001
                return None
    if hasattr(value, "model_dump"):
        try:
            return model_cls.model_validate(value.model_dump())
        except Exception:  # noqa: BLE001
            return None
    return None


# Back-compat alias
get_instrumentation_agent = get_instrumentation_workflow
