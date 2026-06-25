"""A2A Agent Card — the universal descriptor every agent ships.

ard makes agents discoverable by having each server publish an A2A-style
*agent card* at ``/.well-known/agent.json``. This module models that card,
validates it, and serializes to/from the A2A JSON shape.

A small, namespaced ``x-ard`` object records ard-specific facts — notably
whether a server exposes A2A *skills* (a *skill server*) or MCP *tools* (a
*tool server*). Keeping it namespaced means the card stays a valid A2A card
for any consumer that doesn't care about ard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .identity import AuthXIdentity

WELL_KNOWN_PATH = "/.well-known/agent.json"
PROTOCOL_VERSION = "0.2.0"
KINDS = ("skill", "tool")  # an ard server is one of these


class CardError(ValueError):
    """Raised when an agent card is structurally invalid."""


def _require(d: dict, key: str, where: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise CardError(f"{where}: missing required field {key!r}")
    return d[key]


def _require_str(d: dict, key: str, where: str) -> str:
    val = _require(d, key, where)
    if not isinstance(val, str):
        raise CardError(f"{where}: field {key!r} must be a string")
    return val


@dataclass
class AgentSkill:
    """One capability the agent advertises (an A2A skill)."""

    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    input_modes: list[str] | None = None
    output_modes: list[str] | None = None

    def validate(self) -> None:
        if not self.id:
            raise CardError("skill: missing required field 'id'")
        if not self.name:
            raise CardError(f"skill {self.id!r}: missing required field 'name'")
        if not isinstance(self.tags, list):
            raise CardError(f"skill {self.id!r}: 'tags' must be a list")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
        }
        if self.examples:
            d["examples"] = list(self.examples)
        if self.input_modes is not None:
            d["inputModes"] = list(self.input_modes)
        if self.output_modes is not None:
            d["outputModes"] = list(self.output_modes)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentSkill":
        where = f"skill {d.get('id', '?')!r}"
        return cls(
            id=_require_str(d, "id", where),
            name=_require_str(d, "name", where),
            description=str(d.get("description", "")),
            tags=list(d.get("tags", [])),
            examples=list(d.get("examples", [])),
            input_modes=d.get("inputModes"),
            output_modes=d.get("outputModes"),
        )


@dataclass
class AgentCard:
    """An A2A agent card describing a discoverable tool/skill server."""

    name: str
    description: str
    url: str
    version: str
    skills: list[AgentSkill] = field(default_factory=list)
    kind: str = "skill"  # ard extension: "skill" | "tool"
    protocol_version: str = PROTOCOL_VERSION
    provider: dict[str, Any] | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)
    default_input_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    documentation_url: str | None = None
    security_schemes: dict[str, Any] = field(default_factory=dict)
    security: list[dict] = field(default_factory=list)
    identity: AuthXIdentity | None = None

    def validate(self) -> "AgentCard":
        """Validate required fields; returns self so it can be chained."""
        if not self.name:
            raise CardError("card: missing required field 'name'")
        for f in ("description", "url", "version"):
            if not getattr(self, f):
                raise CardError(f"card {self.name!r}: missing required field {f!r}")
        if self.kind not in KINDS:
            raise CardError(f"card {self.name!r}: kind must be one of {KINDS}, got {self.kind!r}")
        if not isinstance(self.skills, list):
            raise CardError(f"card {self.name!r}: 'skills' must be a list")
        ids = set()
        for s in self.skills:
            s.validate()
            if s.id in ids:
                raise CardError(f"card {self.name!r}: duplicate skill id {s.id!r}")
            ids.add(s.id)
        if self.identity is not None:
            self.identity.validate()
        for requirement in self.security:
            for scheme_name in requirement:
                if scheme_name not in self.security_schemes:
                    raise CardError(
                        f"card {self.name!r}: security requires undefined scheme {scheme_name!r}"
                    )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "provider": self.provider,
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                **self.capabilities,
            },
            "defaultInputModes": list(self.default_input_modes),
            "defaultOutputModes": list(self.default_output_modes),
            "skills": [s.to_dict() for s in self.skills],
            "documentationUrl": self.documentation_url,
            "securitySchemes": self.security_schemes,
            "security": self.security,
            "x-ard": {
                "kind": self.kind,
                "identity": self.identity.to_dict() if self.identity else None,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentCard":
        where = f"card {d.get('name', '?')!r}"
        x_ard = d.get("x-ard") or {}
        return cls(
            name=_require_str(d, "name", where),
            description=str(_require(d, "description", where)),
            url=_require_str(d, "url", where),
            version=str(_require(d, "version", where)),
            skills=[AgentSkill.from_dict(s) for s in d.get("skills", [])],
            kind=x_ard.get("kind", "skill"),
            protocol_version=d.get("protocolVersion", PROTOCOL_VERSION),
            provider=d.get("provider"),
            capabilities={k: bool(v) for k, v in (d.get("capabilities") or {}).items()},
            default_input_modes=list(d.get("defaultInputModes", ["text/plain"])),
            default_output_modes=list(d.get("defaultOutputModes", ["text/plain"])),
            documentation_url=d.get("documentationUrl"),
            security_schemes=dict(d.get("securitySchemes") or {}),
            security=list(d.get("security") or []),
            identity=AuthXIdentity.from_dict(x_ard["identity"]) if x_ard.get("identity") else None,
        )

    @classmethod
    def from_json(cls, text: str) -> "AgentCard":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CardError(f"invalid card JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise CardError("card must be a JSON object")
        return cls.from_dict(data)
