"""Bridges to the rest of the AgentWorld (openagx) ecosystem.

ard is the glue layer; these are its connectors:

- **GovernanceSink → openagx/Platform** — stream discovery/deploy events to the
  autonomous-governance feed (ecosystem-wide analogue of the Decision
  Intelligence Console's audit log). The registry emits on register/deregister.
- **to_catalog_entry → openagx/services & openagx/Skills** — project an A2A card
  into a catalog entry, routed by kind (tool → services, skill → Skills).
- **AuthX-ID identity bridge** lives in ``ard/identity.py`` — cards carry an
  identity + ``securitySchemes`` and are discoverable by issuer.
- **Discovery surface (discover.agennext.com)** consumes the registry/API.
"""
from __future__ import annotations

import json
from typing import Protocol, runtime_checkable


@runtime_checkable
class GovernanceSink(Protocol):
    """Anything the registry can stream governance events to (e.g. Platform)."""

    def record(self, event: dict) -> None: ...


class NullSink:
    """Default sink — discards events."""

    def record(self, event: dict) -> None:
        pass


class JsonlSink:
    """Append governance events as JSON lines (a stand-in for the Platform feed)."""

    def __init__(self, path: str) -> None:
        self.path = path

    def record(self, event: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")


# Which openagx repo a server kind is cataloged under.
CATALOG_REPOS = {"tool": "openagx/services", "skill": "openagx/Skills"}


def to_catalog_entry(card) -> dict:
    """Project an agent card into an openagx catalog entry (services / Skills)."""
    return {
        "name": card.name,
        "kind": card.kind,
        "repo": CATALOG_REPOS.get(card.kind, "openagx/services"),
        "url": card.url,
        "version": card.version,
        "skills": [s.id for s in card.skills],
        "identity": card.identity.agent_id if card.identity else None,
        "secured": bool(card.security),
    }
