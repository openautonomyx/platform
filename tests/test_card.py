import pytest

from ard.card import AgentCard, AgentSkill, CardError


def _card(**kw):
    base = dict(
        name="Billing", description="bills", url="http://x", version="1.0", kind="tool",
        skills=[AgentSkill(id="refund", name="Refund", description="r", tags=["pay"])],
    )
    base.update(kw)
    return AgentCard(**base)


def test_valid_card_to_dict():
    d = _card().validate().to_dict()
    assert d["name"] == "Billing"
    assert d["protocolVersion"]
    assert d["x-ard"]["kind"] == "tool"
    assert d["skills"][0]["id"] == "refund"
    assert d["capabilities"]["streaming"] is False
    assert d["defaultInputModes"] == ["text/plain"]


def test_roundtrip_preserves_everything():
    c = _card().validate()
    c2 = AgentCard.from_dict(c.to_dict())
    assert c2.kind == "tool"
    assert c2.to_dict() == c.to_dict()


def test_missing_required_fields():
    with pytest.raises(CardError):
        AgentCard(name="", description="d", url="u", version="1").validate()
    with pytest.raises(CardError):
        AgentCard(name="n", description="", url="u", version="1").validate()


def test_bad_kind_rejected():
    with pytest.raises(CardError):
        _card(kind="weird").validate()


def test_duplicate_skill_id_rejected():
    s = AgentSkill(id="a", name="a", description="")
    with pytest.raises(CardError):
        _card(skills=[s, s]).validate()


def test_skill_requires_id():
    with pytest.raises(CardError):
        AgentSkill(id="", name="x", description="").validate()


def test_from_json_invalid():
    with pytest.raises(CardError):
        AgentCard.from_json("not json")
    with pytest.raises(CardError):
        AgentCard.from_json("[]")
