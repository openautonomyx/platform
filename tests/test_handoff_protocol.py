import base64
import json

import pytest

from handoff_protocol import HandoffBroker, HandoffError, HandoffRequest


def _jwt(claims: dict) -> str:
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'none'})}.{b64(claims)}.s"


def _discover(cards):
    def discover(skill=None, kind=None):
        return [c for c in cards if skill in c.get("skills", [])]
    return discover


CARDS = [{"name": "refunder", "skills": ["refund"], "kind": "tool"}]


def test_route_and_prepare_roundtrip():
    b = HandoffBroker(discover=_discover(CARDS))
    assert b.route("refund")["name"] == "refunder"
    req = b.prepare(from_agent="orchestrator", skill="refund", task={"amount": 50})
    assert req.to_agent == "refunder" and req.task == {"amount": 50}
    assert req.to_dict()["mediaType"].endswith("handoff+json")
    assert HandoffRequest.from_dict(req.to_dict()).to_agent == "refunder"


def test_unroutable_raises():
    with pytest.raises(HandoffError):
        HandoffBroker(discover=_discover([])).prepare(from_agent="o", skill="refund")


def test_multi_hop_trace():
    b = HandoffBroker(discover=_discover(CARDS))
    first = b.prepare(from_agent="A", skill="refund")
    second = b.prepare(from_agent="refunder", skill="refund", prior=first)
    assert second.trace == ["A"]


def test_verify_issuer_and_audience():
    good = HandoffRequest("1", "A", "B", "s", token=_jwt({"iss": "https://id", "aud": "eco"}))
    assert HandoffBroker.verify(good, "https://id", audience="eco") is True
    assert HandoffBroker.verify(good, "https://other") is False
    assert HandoffBroker.verify(HandoffRequest("2", "A", "B", "s"), "https://id") is False


def test_trust_ranking_gate_and_governance():
    cards = [{"name": "low", "skills": ["refund"]}, {"name": "high", "skills": ["refund"]}]
    trust = lambda c: 0.9 if c["name"] == "high" else 0.1  # noqa: E731
    events = []
    b = HandoffBroker(discover=_discover(cards), trust=trust, sink=events.append)
    assert b.route("refund")["name"] == "high"
    assert b.route("refund", min_trust=0.95) is None
    b.accept(b.prepare(from_agent="A", skill="refund"))
    evs = [e["event"] for e in events]
    assert "handoff.prepared" in evs and "handoff.accepted" in evs
