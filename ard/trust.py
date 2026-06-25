"""Agent Trust Score — a transparent 0..1 trust signal for an agent.

Reference for `AGenNext/Agent-Trust-Score`. Trust is computed from *explainable*
factors (identity present, auth required, signed artifact, clean governance
history, …) so a handoff or discovery decision can **prefer** — or **require** —
trustworthy agents. Pairs with agx / No-Trust-Protocol: trust is derived and
earned, never assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .card import AgentCard

# Explainable factor weights (+ a small base). Max = BASE + sum(weights) = 1.0.
BASE = 0.1
WEIGHTS = {"identity": 0.3, "secured": 0.2, "signed": 0.25, "governance_clean": 0.15}


@dataclass
class TrustScore:
    agent: str
    score: float
    factors: dict = field(default_factory=dict)

    def meets(self, threshold: float) -> bool:
        return self.score >= threshold

    def to_dict(self) -> dict:
        return {"agent": self.agent, "score": round(self.score, 4), "factors": self.factors}


def score_card(card: AgentCard, signals: dict | None = None) -> TrustScore:
    """Score an agent from its card + external signals (e.g. Agent-Sign verdict)."""
    signals = signals or {}
    factors = {
        "identity": card.identity is not None,
        "secured": bool(card.security),
        "signed": bool(signals.get("signed")),  # e.g. Agent-Sign / cosign verified
        "governance_clean": bool(signals.get("governance_clean", True)),
    }
    score = BASE + sum(w for k, w in WEIGHTS.items() if factors.get(k))
    return TrustScore(agent=card.name, score=min(1.0, round(score, 4)), factors=factors)
