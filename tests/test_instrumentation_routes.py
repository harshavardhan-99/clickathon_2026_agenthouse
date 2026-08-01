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


def test_instrument_route_success() -> None:
    fake = {
        "status": "ok",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "feature_id": "01_express_checkout",
        "events": [
            {
                "event_name": "express_checkout_shown",
                "journey_order": 1,
                "ch_table": "express_checkout_shown",
                "row_count": 10,
            }
        ],
    }
    with patch(
        "instrumentation_agent.routes.instrumentation.run_instrumentation",
        return_value=fake,
    ):
        response = client.post(
            "/v1/instrument",
            json={"feature_id": "01_express_checkout"},
        )
    assert response.status_code == 200
    assert response.json() == fake


def test_registry_shape() -> None:
    empty = {"feature_id": "01_express_checkout", "feature": None, "events": []}
    with patch(
        "instrumentation_agent.routes.instrumentation.get_feature_registry",
        return_value=empty,
    ):
        response = client.get("/v1/registry/01_express_checkout")
    assert response.status_code == 200
    assert response.json() == empty


def test_health_ok() -> None:
    with (
        patch("instrumentation_agent.routes.health.ping_postgres", return_value=True),
        patch("instrumentation_agent.routes.health.ping_clickhouse", return_value=True),
    ):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "up"
    assert body["clickhouse"] == "up"
    assert "specs_root" in body


def test_instrumentation_tools_construct() -> None:
    from instrumentation_agent.tools.instrumentation import InstrumentationTools

    tools = InstrumentationTools()
    assert tools.name == "instrumentation_tools"
    assert len(tools.tools) >= 2
