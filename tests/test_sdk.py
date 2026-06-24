from ard import Registry, agent_card, discoverable
from ard.card import AgentCard


def test_agent_card_builder_coerces_skills():
    c = agent_card("A", "desc", "http://x", skills=["refund", {"id": "lookup", "tags": ["x"]}])
    assert isinstance(c, AgentCard)
    assert {s.id for s in c.skills} == {"refund", "lookup"}


def test_discoverable_decorator_registers():
    reg = Registry()

    @discoverable(name="Billing", url="http://x", skills=["refund"], kind="tool", registry=reg)
    class Billing:
        """bills"""

    assert Billing.agent_card.name == "Billing"
    assert Billing.agent_card.kind == "tool"
    assert reg.get("Billing") is not None
