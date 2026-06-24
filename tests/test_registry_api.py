from ard import AgentCard, AgentSkill, DiscoveryApi, Registry


def _card(name="A", kind="skill", skill_id="refund", tags=("pay",)):
    return AgentCard(
        name=name, description="d", url="http://x", version="1", kind=kind,
        skills=[AgentSkill(id=skill_id, name=skill_id, description="", tags=list(tags))],
    )


def test_registry_query_by_skill_tag_kind():
    reg = Registry()
    reg.register(_card("A", skill_id="refund", tags=["pay"]))
    reg.register(_card("B", kind="tool", skill_id="search", tags=["web"]))
    assert {c.name for c in reg.query(skill="refund")} == {"A"}
    assert {c.name for c in reg.query(tag="web")} == {"B"}
    assert {c.name for c in reg.query(kind="tool")} == {"B"}
    assert len(reg.query()) == 2


def test_api_lifecycle():
    api = DiscoveryApi(Registry())
    assert api.handle("GET", "/healthz")[0] == 200
    assert api.handle("POST", "/agents", _card("A").to_dict())[0] == 201
    assert len(api.handle("GET", "/agents")[1]) == 1
    assert len(api.handle("GET", "/agents?skill=refund")[1]) == 1
    assert api.handle("GET", "/agents?skill=nope")[1] == []
    assert api.handle("GET", "/agents/A")[1]["name"] == "A"
    assert api.handle("GET", "/agents/missing")[0] == 404
    assert api.handle("DELETE", "/agents/A")[0] == 204
    assert api.handle("GET", "/agents")[1] == []


def test_api_errors():
    api = DiscoveryApi(Registry())
    assert api.handle("POST", "/agents", "notdict")[0] == 400
    assert api.handle("PUT", "/agents")[0] == 405
    assert api.handle("POST", "/agents", {"name": "x"})[0] == 400  # invalid card
