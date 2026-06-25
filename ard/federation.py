"""Federation — peer ard nodes into a discovery mesh ("every repo is a node").

A node federates by querying peer nodes' discovery endpoints and merging the
results with its own registry. No central authority — peers are just URLs.

Transport is injectable, so this is unit-testable offline. By default it fetches
each peer's ``/agents`` list; a peer that only exposes a single card at
``/.well-known/agent.json`` is also supported. Cards are parsed as A2A agent
cards, so this interoperates with the AGenNext registry/console nodes
(`AGenNext/agent-registry`, `AGenNext/agent-console`). Conforming to a peer's
exact published schema beyond the A2A shape is a `fetch`/adapter concern.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from .card import WELL_KNOWN_PATH, AgentCard
from .registry import Registry


def _http_get_json(url: str, timeout: int = 10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (peer URL)
        return json.loads(resp.read().decode())


@dataclass
class Peer:
    url: str  # base URL of a peer node
    name: str | None = None

    def agents_url(self) -> str:
        return self.url.rstrip("/") + "/agents"

    def card_url(self) -> str:
        return self.url.rstrip("/") + WELL_KNOWN_PATH


class Federation:
    """Federated discovery across peer nodes + the local registry."""

    def __init__(self, registry: Registry | None = None, peers=None, fetch=_http_get_json) -> None:
        self.registry = registry or Registry()
        self.peers: list[Peer] = list(peers or [])
        self._fetch = fetch

    def add_peer(self, url: str, name: str | None = None) -> Peer:
        peer = Peer(url=url, name=name)
        if not any(p.url == peer.url for p in self.peers):
            self.peers.append(peer)
        return peer

    def _peer_cards(self, peer: Peer) -> list[AgentCard]:
        try:
            data = self._fetch(peer.agents_url())
        except Exception:
            try:  # a peer may expose only its own well-known card
                data = [self._fetch(peer.card_url())]
            except Exception:
                return []
        if isinstance(data, dict):
            data = [data]
        cards = []
        for d in data or []:
            try:
                cards.append(AgentCard.from_dict(d))
            except Exception:
                continue  # skip anything that isn't a valid card
        return cards

    @staticmethod
    def _matches(card: AgentCard, skill, tag, kind, issuer) -> bool:
        if kind and card.kind != kind:
            return False
        if issuer and not (card.identity and card.identity.issuer == issuer):
            return False
        if skill and not any(s.id == skill or s.name == skill for s in card.skills):
            return False
        if tag and not any(tag in s.tags for s in card.skills):
            return False
        return True

    def discover(self, skill=None, tag=None, kind=None, issuer=None, include_peers=True) -> list[AgentCard]:
        """Merge local + peer results, deduped by agent name (local wins)."""
        by_name = {c.name: c for c in self.registry.query(skill=skill, tag=tag, kind=kind, issuer=issuer)}
        if include_peers:
            for peer in self.peers:
                for card in self._peer_cards(peer):
                    if self._matches(card, skill, tag, kind, issuer):
                        by_name.setdefault(card.name, card)
        return list(by_name.values())
