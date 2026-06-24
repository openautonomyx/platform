import json

from ard import AgentCard, AgentSkill, k8s


def _card():
    return AgentCard(
        name="svc", description="d", url="http://x", version="1", kind="tool",
        skills=[AgentSkill(id="s", name="s", description="")],
    )


def test_manifests_shape():
    ms = k8s.manifests("svc", "img:1", _card(), port=9000)
    assert [m["kind"] for m in ms] == ["Deployment", "Service"]
    container = ms[0]["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "img:1"
    probe = container["readinessProbe"]["httpGet"]
    assert probe["path"] == "/.well-known/agent.json"
    assert probe["port"] == 9000
    assert ms[0]["metadata"]["labels"]["ard.dev/kind"] == "tool"
    assert ms[1]["spec"]["ports"][0]["port"] == 9000


def test_to_json_is_kubectl_list():
    doc = json.loads(k8s.to_json("svc", "img:1", _card()))
    assert doc["kind"] == "List"
    assert len(doc["items"]) == 2
