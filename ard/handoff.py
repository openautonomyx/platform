"""Agent Handoff Protocol — one agent delegates a task to another.

Reference implementation for `AGenNext/Agent-Handoff-Protocol`, built on the
existing ard primitives — no new infrastructure:

  - discovery / federation → find an agent that offers the needed skill
  - A2A cards               → identify source & target
  - identity (AuthX-ID)     → authenticate the handoff
  - governance sink         → record every handoff for audit

Flow:  **discover → prepare → (transmit) → verify → accept/reject → record**

A handoff carries a ``trace`` of prior hops, so multi-hop delegation chains stay
auditable end to end.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .card import AgentCard
from .identity import AuthXIdentity, check_identity

HANDOFF_VERSION = "0.1"
HANDOFF_MEDIA_TYPE = "application/vnd.agentworld.handoff+json"


class HandoffError(ValueError):
    """Raised when a handoff is malformed or unroutable."""


def _trust_value(score) -> float:
    """Accept a TrustScore (has .score) or a bare float."""
    return float(getattr(score, "score", score))


@dataclass
class HandoffRequest:
    id: str
    from_agent: str
    to_agent: str
    skill: str
    task: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    reason: str = ""
    token: str | None = None  # identity token authenticating the source
    trace: list[str] = field(default_factory=list)  # prior agent hops
    version: str = HANDOFF_VERSION

    def validate(self) -> "HandoffRequest":
        for f in ("id", "from_agent", "to_agent", "skill"):
            if not getattr(self, f):
                raise HandoffError(f"handoff: missing required field {f!r}")
        return self

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "mediaType": HANDOFF_MEDIA_TYPE,
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "skill": self.skill,
            "task": self.task,
            "context": self.context,
            "reason": self.reason,
            "token": self.token,
            "trace": list(self.trace),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HandoffRequest":
        return cls(
            id=d.get("id", ""),
            from_agent=d.get("from", ""),
            to_agent=d.get("to", ""),
            skill=d.get("skill", ""),
            task=dict(d.get("task") or {}),
            context=dict(d.get("context") or {}),
            reason=d.get("reason", ""),
            token=d.get("token"),
            trace=list(d.get("trace") or []),
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
    """Routes handoffs over a discovery source and records them for governance.

    ``discover`` is any callable returning ``list[AgentCard]`` for a skill —
    e.g. ``Registry.query`` or ``Federation.discover`` (both accept skill/kind).
    """

    def __init__(self, discover, sink=None, id_factory=None, trust=None) -> None:
        self._discover = discover
        self._sink = sink
        self._id_factory = id_factory
        self._trust = trust  # optional: card -> TrustScore | float (rank & gate targets)
        self._n = 0

    def _next_id(self) -> str:
        if self._id_factory:
            return self._id_factory()
        self._n += 1
        return f"ho-{self._n}"

    def route(self, skill: str, kind: str | None = None, min_trust: float = 0.0) -> AgentCard | None:
        cards = self._discover(skill=skill, kind=kind)
        if not cards:
            return None
        if self._trust:
            best = max(cards, key=lambda c: _trust_value(self._trust(c)))
            return best if _trust_value(self._trust(best)) >= min_trust else None
        return cards[0]

    def prepare(
        self,
        from_agent: str,
        skill: str,
        task: dict | None = None,
        context: dict | None = None,
        reason: str = "",
        token: str | None = None,
        prior: "HandoffRequest | None" = None,
        kind: str | None = None,
        min_trust: float = 0.0,
    ) -> HandoffRequest:
        target = self.route(skill, kind=kind, min_trust=min_trust)
        if target is None:
            raise HandoffError(f"no agent offers skill {skill!r}")
        trace = list(prior.trace) + [prior.from_agent] if prior else []
        req = HandoffRequest(
            id=self._next_id(), from_agent=from_agent, to_agent=target.name, skill=skill,
            task=dict(task or {}), context=dict(context or {}), reason=reason, token=token, trace=trace,
        ).validate()
        self._record("handoff.prepared", req)
        return req

    @staticmethod
    def verify(request: HandoffRequest, identity: AuthXIdentity) -> bool:
        """Receiving side: check the handoff's token against an expected identity."""
        if not request.token:
            return False
        return check_identity(request.token, identity)

    def accept(self, request: HandoffRequest, accepted: bool = True, message: str = "") -> HandoffReceipt:
        self._record("handoff.accepted" if accepted else "handoff.rejected", request)
        return HandoffReceipt(id=request.id, to_agent=request.to_agent, accepted=accepted, message=message)

    def _record(self, event: str, req: HandoffRequest) -> None:
        if self._sink:
            self._sink.record({"event": event, "id": req.id, "from": req.from_agent,
                               "to": req.to_agent, "skill": req.skill})
