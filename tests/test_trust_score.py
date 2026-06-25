from trust_score import score


def test_plain_agent_is_low_trust():
    s = score({"name": "p"})
    assert s.factors["identity"] is False
    assert 0 < s.score < 1
    assert not s.meets(0.9)


def test_full_signals_reach_max():
    agent = {
        "name": "q",
        "security": [{"authx-id": []}],
        "x-ard": {"identity": {"agentId": "agx:q", "issuer": "https://id"}},
    }
    s = score(agent, signals={"signed": True})
    assert s.factors["identity"] and s.factors["secured"] and s.factors["signed"]
    assert s.score == 1.0
    assert s.meets(0.9)
    assert s.to_dict()["agent"] == "q"


def test_object_input_supported():
    class A:
        name = "o"
        identity = object()
        security = [1]

    assert score(A(), signals={"signed": True}).score == 1.0
