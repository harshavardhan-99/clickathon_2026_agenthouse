"""Tests for instrumentation profiler + routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from instrumentation_agent.utils.profiler import (
    flatten_record,
    parse_journey_order,
    profile_feature,
)

client = TestClient(app)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "01_express_checkout"
_SPEC = _FIXTURE / "spec.md"
_EVENTS = _FIXTURE / "events.ndjson"


def test_parse_journey_order_express() -> None:
    order = parse_journey_order(_SPEC.read_text(encoding="utf-8"))
    assert order == [
        "express_checkout_shown",
        "express_checkout_selected",
        "saved_method_used",
        "otp_entered",
        "express_payment_confirmed",
    ]


def test_flatten_nested_payment() -> None:
    flat = flatten_record(
        {"event": "x", "payment": {"amount": 1.0, "latency_ms": 10}}
    )
    assert flat["payment_amount"] == 1.0
    assert flat["payment_latency_ms"] == 10
    assert "payment" not in flat


def test_profile_feature_express() -> None:
    profile = profile_feature("01_express_checkout", _SPEC, _EVENTS)
    assert [e.event_name for e in profile.events] == [
        "express_checkout_shown",
        "express_checkout_selected",
        "saved_method_used",
        "otp_entered",
        "express_payment_confirmed",
    ]
    confirmed = profile.events[-1]
    assert "payment_latency_ms" in confirmed.columns
    assert confirmed.row_count == 1
    assert profile.events[0].row_count == 2


def test_sqlglot_validates_create_ddl() -> None:
    from instrumentation_agent.models.domain import EventProfile
    from instrumentation_agent.utils.clickhouse import build_create_table_sql

    profile = EventProfile(
        event_name="express_checkout_shown",
        journey_order=1,
        columns={"timestamp": "DateTime64(3)", "user_id": "String"},
    )
    ddl = build_create_table_sql(profile, "default")
    assert "CREATE TABLE" in ddl
    assert "MergeTree" in ddl


def test_instrument_route_success() -> None:
    from instrumentation_agent.models.schemas import InstrumentResponse

    fake = InstrumentResponse(
        status="ok",
        run_id="00000000-0000-0000-0000-000000000001",
        feature_id="01_express_checkout",
        events=[
            {
                "event_name": "express_checkout_shown",
                "journey_order": 1,
                "ch_table": "express_checkout_shown",
                "row_count": 10,
            }
        ],
        agent_run_id="agent-run-1",
    )
    with patch(
        "instrumentation_agent.routes.instrumentation.run_instrumentation_agent",
        return_value=fake,
    ):
        response = client.post(
            "/v1/instrument",
            json={"feature_id": "01_express_checkout"},
        )
    assert response.status_code == 200
    assert response.json()["feature_id"] == "01_express_checkout"
    assert response.json()["agent_run_id"] == "agent-run-1"


def test_instrument_route_accepts_dataset_path() -> None:
    from instrumentation_agent.models.schemas import InstrumentResponse

    fake = InstrumentResponse(
        status="ok",
        run_id="00000000-0000-0000-0000-000000000002",
        feature_id="01_express_checkout",
        events=[],
    )
    with patch(
        "instrumentation_agent.routes.instrumentation.run_instrumentation_agent",
        return_value=fake,
    ) as mocked:
        response = client.post(
            "/v1/instrument",
            json={
                "dataset_path": str(_FIXTURE),
                "spec_path": str(_SPEC),
            },
        )
    assert response.status_code == 200
    req = mocked.call_args.args[0]
    assert req.dataset_path == str(_FIXTURE)
    assert req.spec_path == str(_SPEC)


def test_resolve_feature_paths_from_dataset() -> None:
    from instrumentation_agent.utils.paths import resolve_feature_paths

    paths = resolve_feature_paths(dataset_path=_FIXTURE)
    assert paths.feature_id == "01_express_checkout"
    assert paths.events_path == _EVENTS
    assert paths.spec_path == _SPEC
    paths.require_exists()


def test_registry_shape() -> None:
    from instrumentation_agent.models.schemas import RegistryResponse

    empty = RegistryResponse(
        feature_id="01_express_checkout", feature=None, events=[]
    )
    with patch(
        "instrumentation_agent.routes.instrumentation.get_registry",
        return_value=empty,
    ):
        response = client.get("/v1/registry/01_express_checkout")
    assert response.status_code == 200
    assert response.json() == empty.model_dump()


def test_health_ok() -> None:
    from instrumentation_agent.models.schemas import HealthResponse

    fake = HealthResponse(
        status="ok",
        postgres="up",
        clickhouse="up",
        specs_root="/tmp/specs",
    )
    with patch(
        "instrumentation_agent.routes.health.health_check",
        return_value=fake,
    ):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "up"
    assert body["clickhouse"] == "up"


def test_instrumentation_tools_construct() -> None:
    from instrumentation_agent.tools.instrumentation import InstrumentationTools
    from instrumentation_agent.tools.pipeline import PipelineTools

    tools = InstrumentationTools()
    assert tools.name == "instrumentation_tools"
    assert len(tools.tools) >= 2

    pipeline = PipelineTools()
    assert pipeline.name == "pipeline_tools"
    assert len(pipeline.tools) == 4
    inspected = pipeline.inspect_existing_pipeline("01_express_checkout")
    assert '"mock": true' in inspected or '"mock": True' in inspected or '"exists": false' in inspected.lower()


def test_load_spec_workflow_step() -> None:
    from agno.workflow import StepInput

    from instrumentation_agent.agent.orchestration import load_spec_inputs

    out = load_spec_inputs(
        StepInput(
            input={
                "feature_id": None,
                "dataset_path": str(_FIXTURE),
                "spec_path": str(_SPEC),
            }
        )
    )
    assert out.success
    assert isinstance(out.content, str), "agent steps require string content, not dict"
    assert "feature_id: 01_express_checkout" in out.content
    assert "express_checkout_shown" in out.content
    assert "=== spec.md ===" in out.content


def test_instrumentation_workflow_constructs() -> None:
    from instrumentation_agent.agent.orchestration import get_instrumentation_workflow

    get_instrumentation_workflow.cache_clear()
    wf = get_instrumentation_workflow()
    assert wf.name == "Instrumentation"
    assert len(wf.steps) == 3
    assert [s.name for s in wf.steps] == ["load_spec", "summarize_spec", "plan_pipeline"]
