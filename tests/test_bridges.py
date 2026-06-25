import json

from ard import Registry, agent_card
from ard.bridges import JsonlSink, NullSink, to_catalog_entry


def test_registry_emits_governance_events(tmp_path):
    sink_path = tmp_path / "gov.jsonl"
    reg = Registry(sink=JsonlSink(str(sink_path)))
    reg.register(agent_card("A", "d", "http://x", kind="tool", skills=["s"]))
    reg.remove("A")
    events = [json.loads(line) for line in sink_path.read_text().strip().splitlines()]
    assert [e["event"] for e in events] == ["registered", "deregistered"]
    assert events[0]["agent"] == "A" and events[0]["kind"] == "tool"


def test_null_sink_is_the_default():
    reg = Registry()  # NullSink — no error, no output
    reg.register(agent_card("A", "d", "http://x", skills=["s"]))
    assert reg.get("A") is not None


def test_catalog_targets_agennext_registry():
    tool = agent_card("T", "d", "http://x", kind="tool", skills=["search"])
    skill = agent_card("S", "d", "http://x", kind="skill", skills=["echo"])
    assert to_catalog_entry(tool)["registry"] == "AGenNext/Agent-MCPs"
    assert to_catalog_entry(tool)["kind"] == "tool"
    assert to_catalog_entry(skill)["kind"] == "skill"
    assert to_catalog_entry(tool)["skills"] == ["search"]
