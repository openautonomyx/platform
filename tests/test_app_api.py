"""Tests for the web app's request router (``app.api.Api``).

The router is transport-independent, so these exercise the full HTTP surface
without opening a socket — just construct an :class:`Api` over a fresh
:class:`~app.registry.Registry` and call ``handle``.
"""
import json

import pytest

from app import Api, Registry


@pytest.fixture
def api() -> Api:
    return Api(Registry())


def _post(api: Api, path: str, payload: dict):
    return api.handle("POST", path, json.dumps(payload).encode())


# --- health & models ------------------------------------------------------

def test_health_ok(api):
    resp = api.handle("GET", "/api/health")
    assert resp.status == 200
    assert resp.json()["status"] == "ok"


def test_list_models_includes_seeded(api):
    resp = api.handle("GET", "/api/models")
    assert resp.status == 200
    names = {m["name"] for m in resp.json()}
    assert {"credit", "risk", "routing"} <= names


def test_get_model_returns_rules(api):
    resp = api.handle("GET", "/api/models/credit")
    body = resp.json()
    assert resp.status == 200
    assert body["inputs"] == ["score", "amount"]
    assert {r["name"] for r in body["rules"]} == {"auto-decline", "auto-approve"}


def test_get_unknown_model_404(api):
    resp = api.handle("GET", "/api/models/nope")
    assert resp.status == 404
    assert "error" in resp.json()


# --- decide ---------------------------------------------------------------

def test_decide_matches_rule_with_trace(api):
    resp = _post(api, "/api/decide", {"model": "credit", "inputs": {"score": 750, "amount": 5000}})
    body = resp.json()
    assert resp.status == 200
    assert body["outcome"] == "approve"
    assert body["matched_rule"] == "auto-approve"
    assert body["matched"] is True
    assert {t["rule"] for t in body["trace"]} == {"auto-decline", "auto-approve"}


def test_decide_falls_back_to_default(api):
    resp = _post(api, "/api/decide", {"model": "credit", "inputs": {"score": 600, "amount": 5000}})
    body = resp.json()
    assert body["outcome"] == "manual_review"
    assert body["matched"] is False
    assert body["matched_rule"] is None


def test_decide_missing_declared_input_is_400(api):
    resp = _post(api, "/api/decide", {"model": "credit", "inputs": {"score": 750}})
    assert resp.status == 400
    assert "amount" in resp.json()["error"]


def test_decide_records_to_audit_log(api):
    _post(api, "/api/decide", {"model": "credit", "inputs": {"score": 750, "amount": 5000}})
    resp = api.handle("GET", "/api/audit")
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["model"] == "credit"
    assert entries[0]["outcome"] == "approve"


# --- model registration ---------------------------------------------------

def test_register_then_decide_on_new_model(api):
    model = {
        "name": "vip",
        "inputs": ["tier"],
        "default_outcome": "standard",
        "rules": [
            {"name": "gold", "conditions": [{"field": "tier", "operator": "eq", "value": "gold"}], "outcome": "priority"}
        ],
    }
    created = _post(api, "/api/models", model)
    assert created.status == 200
    resp = _post(api, "/api/decide", {"model": "vip", "inputs": {"tier": "gold"}})
    assert resp.json()["outcome"] == "priority"


def test_register_unknown_operator_is_400(api):
    model = {"name": "bad", "rules": [{"name": "r", "conditions": [{"field": "x", "operator": "wat", "value": 1}], "outcome": "y"}]}
    resp = _post(api, "/api/models", model)
    assert resp.status == 400
    assert "operator" in resp.json()["error"]


# --- flows / orchestration ------------------------------------------------

def test_flow_risk_to_routing_high_path(api):
    payload = {
        "steps": [
            {"service": "risk"},
            {"service": "routing", "mapper": {"risk": "risk_outcome"}},
        ],
        "inputs": {"amount": 50000},
    }
    resp = _post(api, "/api/flows/run", payload)
    body = resp.json()
    assert resp.status == 200
    assert body["results"]["risk"]["outcome"] == "high"
    assert body["results"]["routing"]["outcome"] == "human"
    assert body["final_outcome"] == "human"


def test_flow_low_risk_routes_to_auto(api):
    payload = {
        "steps": [
            {"service": "risk"},
            {"service": "routing", "mapper": {"risk": "risk_outcome"}},
        ],
        "inputs": {"amount": 100},
    }
    body = _post(api, "/api/flows/run", payload).json()
    assert body["final_outcome"] == "auto"


def test_empty_flow_is_400(api):
    resp = _post(api, "/api/flows/run", {"steps": [], "inputs": {}})
    assert resp.status == 400


def test_flow_records_each_step_to_audit(api):
    payload = {
        "steps": [{"service": "risk"}, {"service": "routing", "mapper": {"risk": "risk_outcome"}}],
        "inputs": {"amount": 50000},
    }
    _post(api, "/api/flows/run", payload)
    entries = api.handle("GET", "/api/audit").json()
    assert {e["model"] for e in entries} == {"risk", "routing"}


def test_audit_filter_by_model(api):
    _post(api, "/api/decide", {"model": "credit", "inputs": {"score": 800, "amount": 1000}})
    _post(api, "/api/decide", {"model": "risk", "inputs": {"amount": 50000}})
    only_risk = api.handle("GET", "/api/audit?model=risk").json()
    assert len(only_risk) == 1
    assert only_risk[0]["model"] == "risk"


# --- protocol-level behaviour ---------------------------------------------

def test_bad_json_body_is_400(api):
    resp = api.handle("POST", "/api/decide", b"{not json")
    assert resp.status == 400


def test_unknown_endpoint_is_404(api):
    resp = api.handle("GET", "/api/nope")
    assert resp.status == 404


def test_wrong_method_is_405(api):
    resp = api.handle("POST", "/api/audit", b"{}")
    assert resp.status == 405


def test_serves_index_html(api):
    resp = api.handle("GET", "/")
    assert resp.status == 200
    assert resp.content_type.startswith("text/html")
    assert b"Decision Intelligence Console" in resp.body


def test_static_path_traversal_blocked(api):
    resp = api.handle("GET", "/static/../registry.py")
    assert resp.status == 404
