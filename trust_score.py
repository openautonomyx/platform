"""Agent Trust Score — a transparent 0..1 trust signal for an agent.

Standalone, stdlib-only reference implementation for AGenNext/Agent-Trust-Score
(mirrors ard/trust.py). `score()` accepts an A2A-style agent card as a dict
(`{"name", "security", "x-ard": {"identity": ...}}`) OR any object with
`name`/`identity`/`security` attributes — so it works with or without `ard`.

Trust is derived from explainable factors (identity present, auth required,
signed artifact, clean governance) — never assumed. Pairs with No-Trust-Protocol.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BASE = 0.1
WEIGHTS = {"identity": 0.3, "secured": 0.2, "signed": 0.25, "governance_clean": 0.15}


def _get(agent, name, default=None):
    if isinstance(agent, dict):
        if name == "identity":
            return (agent.get("x-ard") or {}).get("identity") or agent.get("identity")
        return agent.get(name, default)
    return getattr(agent, name, default)


@dataclass
class TrustScore:
    agent: str
    score: float
    factors: dict = field(default_factory=dict)

    def meets(self, threshold: float) -> bool:
        return self.score >= threshold

    def to_dict(self) -> dict:
        return {"agent": self.agent, "score": round(self.score, 4), "factors": self.factors}


def score(agent, signals: dict | None = None) -> TrustScore:
    """Score an agent from its card + external signals (e.g. an Agent-Sign verdict)."""
    signals = signals or {}
    factors = {
        "identity": bool(_get(agent, "identity")),
        "secured": bool(_get(agent, "security")),
        "signed": bool(signals.get("signed")),
        "governance_clean": bool(signals.get("governance_clean", True)),
    }
    value = BASE + sum(w for k, w in WEIGHTS.items() if factors.get(k))
    return TrustScore(agent=_get(agent, "name", "") or "", score=min(1.0, round(value, 4)), factors=factors)
