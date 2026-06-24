from ard import AgentCard, AgentSkill, Registry
from ard.pod import FakeRuntime, ManifestRuntime, PodManager, PodSpec


def _card():
    return AgentCard(
        name="agentA", description="d", url="http://x", version="1", kind="skill",
        skills=[AgentSkill(id="s", name="s", description="")],
    )


def _spec():
    return PodSpec(name="agentA", image="img:1", card=_card(), kind="skill", port=8080)


def test_deploy_registers_and_tracks():
    reg, rt = Registry(), FakeRuntime()
    mgr = PodManager(runtime=rt, registry=reg)
    pod = mgr.deploy(_spec())
    assert pod.status == "running"
    assert "agentA" in rt.started
    assert reg.get("agentA") is not None  # deployed → discoverable
    assert [p.name for p in mgr.list()] == ["agentA"]


def test_stop_transitions_state():
    rt = FakeRuntime()
    mgr = PodManager(runtime=rt)
    mgr.deploy(_spec())
    assert mgr.stop("agentA") is True
    assert "agentA" in rt.stopped
    assert mgr.status("agentA").status == "stopped"
    assert mgr.stop("nope") is False


def test_manifest_output():
    mgr = PodManager(runtime=ManifestRuntime())
    doc = mgr.manifests(_spec())
    assert doc["kind"] == "List" and len(doc["items"]) == 2


def test_state_persists_across_managers(tmp_path):
    state = str(tmp_path / "pods.json")
    PodManager(runtime=FakeRuntime(), state_path=state).deploy(_spec())
    reloaded = PodManager(runtime=ManifestRuntime(), state_path=state)
    assert [p.name for p in reloaded.list()] == ["agentA"]
