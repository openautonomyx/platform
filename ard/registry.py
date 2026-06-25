"""The ecosystem hub: a registry of agent cards with discovery queries.

Cards can be registered explicitly (an agent pushing its card on deploy) or
discovered by crawling ``/.well-known/agent.json`` endpoints. State optionally
persists to a JSON file so a long-running registry survives restarts.
"""
from __future__ import annotations

import json
import os
import threading

from .bridges import NullSink
from .card import AgentCard


class Registry:
    def __init__(self, path: str | None = None, sink=None) -> None:
        self._lock = threading.Lock()
        self._cards: dict[str, AgentCard] = {}
        self.path = path
        self.sink = sink or NullSink()
        if path and os.path.exists(path):
            self._load()

    def register(self, card: AgentCard) -> AgentCard:
        card.validate()
        with self._lock:
            self._cards[card.name] = card
            self._save()
        self.sink.record({"event": "registered", "agent": card.name, "kind": card.kind, "url": card.url})
        return card

    def get(self, name: str) -> AgentCard | None:
        with self._lock:
            return self._cards.get(name)

    def all(self) -> list[AgentCard]:
        with self._lock:
            return list(self._cards.values())

    def remove(self, name: str) -> bool:
        with self._lock:
            existed = self._cards.pop(name, None) is not None
            self._save()
        if existed:
            self.sink.record({"event": "deregistered", "agent": name})
        return existed

    def query(
        self,
        skill: str | None = None,
        tag: str | None = None,
        kind: str | None = None,
        issuer: str | None = None,
    ) -> list[AgentCard]:
        """Find cards by skill id/name, skill tag, server kind, and/or AuthX-ID issuer."""
        results = []
        for card in self.all():
            if kind and card.kind != kind:
                continue
            if issuer and not (card.identity and card.identity.issuer == issuer):
                continue
            if skill and not any(s.id == skill or s.name == skill for s in card.skills):
                continue
            if tag and not any(tag in s.tags for s in card.skills):
                continue
            results.append(card)
        return results

    # --- persistence ------------------------------------------------------

    def _save(self) -> None:
        if not self.path:
            return
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in self._cards.values()], f, indent=2)

    def _load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            card = AgentCard.from_dict(d)
            self._cards[card.name] = card
