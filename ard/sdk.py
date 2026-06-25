"""Tiny SDK — make an agent discoverable in a couple of lines.

This is the per-agent adoption surface. Most agents will get their card wired
in automatically by the buildpack at build time, but the decorator is handy for
declaring skills in code and registering with a local registry in dev.
"""
from __future__ import annotations

from typing import Any

from .card import AgentCard, AgentSkill
from .identity import AuthXIdentity, secure_with_authx
from .registry import Registry


def _coerce_skill(s: Any) -> AgentSkill:
    if isinstance(s, AgentSkill):
        return s
    if isinstance(s, str):
        return AgentSkill(id=s, name=s, description=s)
    if isinstance(s, dict):
        return AgentSkill(
            id=s["id"],
            name=s.get("name", s["id"]),
            description=s.get("description", ""),
            tags=list(s.get("tags", [])),
            examples=list(s.get("examples", [])),
        )
    raise TypeError(f"cannot interpret {s!r} as a skill")


def _coerce_identity(identity) -> AuthXIdentity | None:
    if identity is None or isinstance(identity, AuthXIdentity):
        return identity
    if isinstance(identity, dict):
        return AuthXIdentity.from_dict(identity)
    raise TypeError(f"cannot interpret {identity!r} as an AuthXIdentity")


def agent_card(
    name: str,
    description: str,
    url: str,
    version: str = "0.1.0",
    kind: str = "skill",
    skills: list | None = None,
    identity=None,
    secured: bool = False,
) -> AgentCard:
    ident = _coerce_identity(identity)
    card = AgentCard(
        name=name,
        description=description,
        url=url,
        version=version,
        kind=kind,
        skills=[_coerce_skill(s) for s in (skills or [])],
        identity=ident,
    )
    if secured:
        if ident is None:
            raise ValueError("secured=True requires an identity")
        card.security_schemes, card.security = secure_with_authx(ident)
    return card.validate()


def discoverable(
    *,
    name: str | None = None,
    description: str = "",
    url: str = "http://localhost:8080",
    version: str = "0.1.0",
    kind: str = "skill",
    skills: list | None = None,
    identity=None,
    secured: bool = False,
    registry: Registry | None = None,
):
    """Attach an A2A card to a class/function and (optionally) register it."""

    def decorate(obj):
        resolved = name or getattr(obj, "__name__", obj.__class__.__name__)
        desc = description or (getattr(obj, "__doc__", "") or "").strip() or resolved
        card = agent_card(resolved, desc, url, version, kind, skills, identity=identity, secured=secured)
        obj.agent_card = card
        if registry is not None:
            registry.register(card)
        return obj

    return decorate
