"""Agent Handoff Protocol — one agent delegates a task to another.

Standalone, stdlib-only reference implementation for AGenNext/Agent-Handoff-Protocol
(mirrors ard/handoff.py). No external deps:

  - `discover` is any callable returning a list of agent cards — a dict with
    `"name"`/`"skills"` or an object with `.name` (e.g. from a registry).
  - identity verification reads (unverified) JWT claims — MVP; real verification
    checks the issuer's JWKS signature.
  - a trust scorer (card -> float | obj with .score) ranks & gates targets.

Flow:  discover -> prepare -> transmit -> verify -> accept/reject -> record
"""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field

HANDOFF_VERSION = "0.1"
HANDOFF_MEDIA_TYPE = "application/vnd.agentworld.handoff+json"


class HandoffError(ValueError):
    """Raised when a handoff is malformed or unroutable."""


def _name(card):
    return card.get("name") if isinstance(card, dict) else getattr(card, "name", None)


def _trust_value(s) -> float:
    return float(getattr(s, "score", s))


def unverified_claims(token: str) -> dict:
    """Decode a JWT payload WITHOUT verifying the signature (MVP only)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, binascii.Error, json.JSONDecodeError, ValueError):
        return {}


@dataclass
class HandoffRequest:
    id: str
    from_agent: str
    to_agent: str
    skill: str
    task: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    reason: str = ""
    token: str | None = None
    trace: list = field(default_factory=list)
    version: str = HANDOFF_VERSION

    def validate(self) -> "HandoffRequest":
        for f in ("id", "from_agent", "to_agent", "skill"):
            if not getattr(self, f):
                raise HandoffError(f"handoff: missing required field {f!r}")
        return self

    def to_dict(self) -> dict:
        return {
            "version": self.version, "mediaType": HANDOFF_MEDIA_TYPE, "id": self.id,
            "from": self.from_agent, "to": self.to_agent, "skill": self.skill,
            "task": self.task, "context": self.context, "reason": self.reason,
            "token": self.token, "trace": list(self.trace),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HandoffRequest":
        return cls(
            id=d.get("id", ""), from_agent=d.get("from", ""), to_agent=d.get("to", ""),
            skill=d.get("skill", ""), task=dict(d.get("task") or {}), context=dict(d.get("context") or {}),
            reason=d.get("reason", ""), token=d.get("token"), trace=list(d.get("trace") or []),
            version=d.get("version", HANDOFF_VERSION),
        ).validate()


@dataclass
class HandoffReceipt:
    id: str
    to_agent: str
    accepted: bool
    message: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "to": self.to_agent, "accepted": self.accepted, "message": self.message}


class HandoffBroker:
    def __init__(self, discover, sink=None, id_factory=None, trust=None) -> None:
        self._discover = discover
        self._sink = sink  # callable(event_dict) -> None
        self._id_factory = id_factory
        self._trust = trust
        self._n = 0

    def _next_id(self) -> str:
        if self._id_factory:
            return self._id_factory()
        self._n += 1
        return f"ho-{self._n}"

    def route(self, skill: str, kind: str | None = None, min_trust: float = 0.0):
        cards = self._discover(skill=skill, kind=kind)
        if not cards:
            return None
        if self._trust:
            best = max(cards, key=lambda c: _trust_value(self._trust(c)))
            return best if _trust_value(self._trust(best)) >= min_trust else None
        return cards[0]

    def prepare(self, from_agent, skill, task=None, context=None, reason="",
                token=None, prior=None, kind=None, min_trust=0.0) -> HandoffRequest:
        target = self.route(skill, kind=kind, min_trust=min_trust)
        if target is None:
            raise HandoffError(f"no agent offers skill {skill!r}")
        trace = list(prior.trace) + [prior.from_agent] if prior else []
        req = HandoffRequest(
            id=self._next_id(), from_agent=from_agent, to_agent=_name(target), skill=skill,
            task=dict(task or {}), context=dict(context or {}), reason=reason, token=token, trace=trace,
        ).validate()
        self._record("handoff.prepared", req)
        return req

    @staticmethod
    def verify(request: HandoffRequest, issuer: str, audience: str | None = None) -> bool:
        """Receiving side: check the handoff token's issuer (+ audience). MVP: no signature check."""
        if not request.token:
            return False
        claims = unverified_claims(request.token)
        if claims.get("iss") != issuer:
            return False
        if audience:
            aud = claims.get("aud")
            auds = aud if isinstance(aud, list) else [aud]
            if audience not in auds:
                return False
        return True

    def accept(self, request: HandoffRequest, accepted: bool = True, message: str = "") -> HandoffReceipt:
        self._record("handoff.accepted" if accepted else "handoff.rejected", request)
        return HandoffReceipt(id=request.id, to_agent=request.to_agent, accepted=accepted, message=message)

    def _record(self, event: str, req: HandoffRequest) -> None:
        if self._sink:
            self._sink({"event": event, "id": req.id, "from": req.from_agent,
                        "to": req.to_agent, "skill": req.skill})
