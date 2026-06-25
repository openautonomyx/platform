from ard import Registry, agent_card
from ard.federation import Federation, Peer


def _fake_fetch(mapping):
    def fetch(url):
        if url in mapping:
            return mapping[url]
        raise OSError(f"no route: {url}")
    return fetch


def test_federated_discovery_merges_peers():
    local = Registry()
    local.register(agent_card("local-a", "d", "http://x", skills=["s"]))
    peer_cards = [agent_card("peer-b", "d", "http://y", kind="tool", skills=["search"]).to_dict()]
    fed = Federation(
        registry=local,
        peers=[Peer("http://peer1")],
        fetch=_fake_fetch({"http://peer1/agents": peer_cards}),
    )
    assert {c.name for c in fed.discover()} == {"local-a", "peer-b"}


def test_local_wins_on_name_collision():
    local = Registry()
    local.register(agent_card("dup", "LOCAL", "http://x", skills=["s"]))
    peer = [agent_card("dup", "PEER", "http://y", skills=["s"]).to_dict()]
    fed = Federation(registry=local, peers=[Peer("http://p")], fetch=_fake_fetch({"http://p/agents": peer}))
    got = {c.name: c.description for c in fed.discover()}
    assert got["dup"] == "LOCAL"


def test_filter_applies_across_peers():
    cards = [
        agent_card("t", "d", "http://y", kind="tool", skills=["search"]).to_dict(),
        agent_card("s", "d", "http://y", kind="skill", skills=["echo"]).to_dict(),
    ]
    fed = Federation(peers=[Peer("http://p")], fetch=_fake_fetch({"http://p/agents": cards}))
    assert {c.name for c in fed.discover(kind="tool")} == {"t"}


def test_fallback_to_well_known_card():
    card = agent_card("solo", "d", "http://y", skills=["s"]).to_dict()
    fed = Federation(peers=[Peer("http://p")], fetch=_fake_fetch({"http://p/.well-known/agent.json": card}))
    assert {c.name for c in fed.discover()} == {"solo"}


def test_add_peer_dedupes():
    fed = Federation(fetch=lambda u: [])
    fed.add_peer("http://p")
    fed.add_peer("http://p")
    assert len(fed.peers) == 1


def test_unreachable_peer_is_skipped():
    fed = Federation(peers=[Peer("http://down")], fetch=_fake_fetch({}))
    assert fed.discover() == []
