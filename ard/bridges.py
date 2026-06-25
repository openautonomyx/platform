"""Bridges to the rest of the AgentWorld (openagx) ecosystem.

ard is the glue layer; these are its connectors:

- **GovernanceSink → agx (igsec security & governance platform)** — stream
  discovery/deploy events to the autonomous-governance feed (ecosystem-wide
  analogue of the Console's audit log). The registry emits on register/deregister.
- **to_catalog_entry → AGenNext/Agent-MCPs** — project an A2A card into a
  registry entry (the AGenNext agent/MCP registry), tagged by kind.
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


# The AGenNext registry that tool and skill servers are cataloged in.
REGISTRY_REPO = "AGenNext/Agent-MCPs"


def to_catalog_entry(card) -> dict:
    """Project an agent card into an AGenNext registry (Agent-MCPs) entry."""
    return {
        "name": card.name,
        "kind": card.kind,
        "registry": REGISTRY_REPO,
        "url": card.url,
        "version": card.version,
        "skills": [s.id for s in card.skills],
        "identity": card.identity.agent_id if card.identity else None,
        "secured": bool(card.security),
    }
