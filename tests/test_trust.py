from ard import AuthXIdentity, Registry, agent_card
from ard.handoff import HandoffBroker
from ard.trust import score_card


def test_score_factors_are_explainable():
    plain = agent_card("p", "d", "http://x", skills=["s"])
    s = score_card(plain)
    assert 0 < s.score < 1
    assert s.factors["identity"] is False

    secured = agent_card(
        "q", "d", "http://x", skills=["s"], identity=AuthXIdentity("agx:q", "https://id"), secured=True
    )
    s2 = score_card(secured, signals={"signed": True})
    assert s2.factors["identity"] and s2.factors["secured"] and s2.factors["signed"]
    assert s2.score == 1.0  # base + identity + secured + signed + governance_clean
    assert s2.meets(0.9) and not s.meets(0.9)


def test_route_prefers_higher_trust():
    reg = Registry()
    reg.register(agent_card("low", "d", "http://x", kind="tool", skills=["refund"]))
    reg.register(agent_card(
        "high", "d", "http://x", kind="tool", skills=["refund"],
        identity=AuthXIdentity("agx:h", "https://id"), secured=True,
    ))
    broker = HandoffBroker(discover=reg.query, trust=lambda c: score_card(c, signals={"signed": True}))
    assert broker.route("refund").name == "high"


def test_min_trust_gate_filters_low_trust():
    reg = Registry()
    reg.register(agent_card("low", "d", "http://x", kind="tool", skills=["refund"]))
    broker = HandoffBroker(discover=reg.query, trust=score_card)
    assert broker.route("refund", min_trust=0.9) is None
