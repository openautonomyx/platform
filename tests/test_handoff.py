import base64
import json

import pytest

from ard import AuthXIdentity, Registry, agent_card
from ard.bridges import JsonlSink
from ard.handoff import HandoffBroker, HandoffError, HandoffRequest


def _jwt(claims: dict) -> str:
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'none'})}.{b64(claims)}.s"


def _reg():
    r = Registry()
    r.register(agent_card("refunder", "d", "http://x", kind="tool", skills=["refund"]))
    return r


def test_route_finds_skill():
    b = HandoffBroker(discover=_reg().query)
    assert b.route("refund").name == "refunder"
    assert b.route("nope") is None


def test_prepare_targets_discovered_agent_and_roundtrips():
    b = HandoffBroker(discover=_reg().query)
    req = b.prepare(from_agent="orchestrator", skill="refund", task={"amount": 50})
    assert (req.to_agent, req.from_agent, req.skill) == ("refunder", "orchestrator", "refund")
    assert req.id and req.task == {"amount": 50}
    d = req.to_dict()
    assert d["mediaType"].endswith("handoff+json")
    assert HandoffRequest.from_dict(d).to_agent == "refunder"


def test_prepare_without_target_raises():
    b = HandoffBroker(discover=Registry().query)
    with pytest.raises(HandoffError):
        b.prepare(from_agent="o", skill="refund")


def test_multi_hop_trace():
    b = HandoffBroker(discover=_reg().query)
    first = b.prepare(from_agent="A", skill="refund")          # A → refunder
    second = b.prepare(from_agent="refunder", skill="refund", prior=first)
    assert second.trace == ["A"]


def test_verify_identity_token():
    ident = AuthXIdentity("agx:a", "https://authx.openagx.dev")
    good = HandoffRequest("1", "A", "B", "s", token=_jwt({"iss": "https://authx.openagx.dev"}))
    bad = HandoffRequest("2", "A", "B", "s", token=_jwt({"iss": "https://evil"}))
    none = HandoffRequest("3", "A", "B", "s")
    assert HandoffBroker.verify(good, ident) is True
    assert HandoffBroker.verify(bad, ident) is False
    assert HandoffBroker.verify(none, ident) is False


def test_governance_records_handoff(tmp_path):
    sink = JsonlSink(str(tmp_path / "g.jsonl"))
    b = HandoffBroker(discover=_reg().query, sink=sink)
    req = b.prepare(from_agent="A", skill="refund")
    b.accept(req, accepted=True)
    events = [json.loads(line)["event"] for line in (tmp_path / "g.jsonl").read_text().splitlines()]
    assert "handoff.prepared" in events and "handoff.accepted" in events
