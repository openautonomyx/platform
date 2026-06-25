"""agx-ADR — Agentic Detection & Response (reference sketch).

A faithful, dependency-free sketch of the ADR architecture (arXiv 2605.17380,
"ADR: An Agentic Detection System for Enterprise Agentic AI Security") for the
**agx** security plane. It consumes the Agent-Discovery (ard) layer:

  - ard's **MCP registry** (`ard mcp-registry`) tells the Detector what tools
    exist and what they do (Tier-2 context).
  - ard's **governance feed** (register/deploy/handoff + agent telemetry) is the
    Sensor's input.

Three components (mirroring the paper):
  - **Sensor**   — normalize telemetry into a causal chain
                   (prompt → reasoning → tool calls → outcome + env).
  - **Detector** — two-tier: Tier-1 fast triage (high recall, cheap heuristics)
                   → Tier-2 context-aware reasoning (precision-first), with a
                   pluggable LLM `reasoner` + threat-intel / policy providers.
  - **Explorer** — offline evolutionary red-teaming; fitness ``F = ε·σ·τ**α``;
                   converges when ``survival·mutations < 1``; publishes
                   threat intel back to the Detector (closing the loop).

Deterministic (no RNG), stdlib only.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Sensor: telemetry -> causal chain
# --------------------------------------------------------------------------


@dataclass
class ToolCall:
    tool: str
    args: dict = field(default_factory=dict)
    result: str = ""


@dataclass
class Session:
    id: str
    prompt: str = ""
    reasoning: str = ""
    tool_calls: list = field(default_factory=list)  # list[ToolCall]
    env: dict = field(default_factory=dict)


class Sensor:
    """Normalize a telemetry/governance event into a Session (causal chain)."""

    @staticmethod
    def from_event(event: dict) -> Session:
        calls = []
        for tc in event.get("tool_calls", []):
            if isinstance(tc, ToolCall):
                calls.append(tc)
            else:
                calls.append(ToolCall(tool=tc.get("tool", ""), args=tc.get("args") or {}, result=tc.get("result", "") or ""))
        return Session(
            id=str(event.get("id", "")),
            prompt=event.get("prompt", ""),
            reasoning=event.get("reasoning", ""),
            tool_calls=calls,
            env=dict(event.get("env", {})),
        )


# --------------------------------------------------------------------------
# Tier 1: triage (fast, high recall)
# --------------------------------------------------------------------------

_SECRET_RE = re.compile(
    r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_INJECTION = ("ignore previous", "ignore all previous", "disregard your", "exfiltrate", "do not tell", "override the")
_SENSITIVE = (".ssh", "id_rsa", ".aws", "credentials", ".env", "secrets", "private key")
_EXFIL = ("http", "curl", "fetch", "request", "upload", "email", "send", "post")


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _has_secret(text: str) -> bool:
    if _SECRET_RE.search(text):
        return True
    return any(_entropy(tok) >= 4.0 for tok in re.findall(r"[A-Za-z0-9_\-/+=]{20,}", text))


def triage(session: Session) -> dict:
    """Tier-1 heuristics → {suspicious, signals}. Conservative: when in doubt, flag."""
    signals = []
    text = f"{session.prompt}\n{session.reasoning}"
    results = " ".join(tc.result for tc in session.tool_calls)
    low = text.lower()
    if any(p in low for p in _INJECTION):
        signals.append("prompt_injection")
    if _has_secret(text + "\n" + results):
        signals.append("secret_pattern")
    blob = " ".join((tc.tool + " " + str(tc.args)).lower() for tc in session.tool_calls)
    sensitive = any(s in blob for s in _SENSITIVE)
    exfil = any(t in tc.tool.lower() for tc in session.tool_calls for t in _EXFIL)
    if sensitive:
        signals.append("sensitive_access")
    if sensitive and exfil:
        signals.append("access_then_exfil")
    return {"suspicious": bool(signals), "signals": signals}


# --------------------------------------------------------------------------
# Threat intelligence + Tier 2 reasoning
# --------------------------------------------------------------------------


@dataclass
class Verdict:
    session_id: str
    malicious: bool
    confidence: float
    tactic: str | None
    rationale: str
    tier: int


@dataclass
class ThreatEntry:
    technique: str
    signal: str
    guidance: str
    source: str = "CURATED"  # or "EAS" (Explorer-discovered)


class ThreatIntel:
    def __init__(self) -> None:
        self._entries: list[ThreatEntry] = []

    def add(self, entry: ThreatEntry) -> None:
        self._entries.append(entry)

    def for_signal(self, signal: str) -> list[ThreatEntry]:
        return [e for e in self._entries if e.signal == signal]

    def __len__(self) -> int:
        return len(self._entries)


# strong signal -> (tactic, confidence), in precedence order
_STRONG = (
    ("access_then_exfil", "Reasoning & Data Manipulation", 0.95),
    ("secret_pattern", "Operational Impact", 0.90),
    ("prompt_injection", "Initial Access & Execution", 0.80),
)


class Detector:
    """Two-tier detector: Tier-1 triage → Tier-2 reasoning (precision-first)."""

    def __init__(self, threat_intel: ThreatIntel | None = None, policy=None, reasoner=None) -> None:
        self.threat_intel = threat_intel or ThreatIntel()
        self.policy = policy        # callable(session) -> list[str] violations
        self.reasoner = reasoner    # callable(session, triage, threat_intel, policy) -> Verdict

    def detect(self, session: Session) -> Verdict:
        t = triage(session)
        if not t["suspicious"]:
            return Verdict(session.id, False, 0.0, None, "tier1: clearly benign", 1)
        if self.reasoner:
            return self.reasoner(session, t, self.threat_intel, self.policy)
        return self._reason(session, t)

    def _reason(self, session: Session, t: dict) -> Verdict:
        signals = t["signals"]
        for sig, tactic, conf in _STRONG:
            if sig in signals:
                if self.threat_intel.for_signal(sig):
                    conf = min(1.0, conf + 0.05)
                return Verdict(session.id, True, conf, tactic, f"tier2: {sig}", 2)
        # threat-intel-only match (e.g. a subtle signal the Explorer flagged)
        for sig in signals:
            hits = self.threat_intel.for_signal(sig)
            if hits:
                return Verdict(session.id, True, 0.75, hits[0].technique, f"tier2: threat-intel {sig}", 2)
        # suspicious but inconclusive → escalate to human, not auto-malicious
        return Verdict(session.id, False, 0.4, None, f"tier2: escalate ({','.join(signals)})", 2)


# --------------------------------------------------------------------------
# Explorer: offline evolutionary red-teaming
# --------------------------------------------------------------------------


@dataclass
class AttackVariant:
    id: str
    technique: str
    signal: str            # the triage signal this attack rides on
    session: dict          # synthesized telemetry
    depth: float = 1.0     # ε: how far the attack progresses
    naturalness: float = 1.0  # σ: how benign it appears
    impact: float = 1.0    # τ: damage potential
    evaded: bool = False


def fitness(v: AttackVariant, alpha: float = 1.2) -> float:
    """F = ε · σ · τ**α — weights impact more strongly (α > 1)."""
    return v.depth * v.naturalness * (v.impact ** alpha)


class Explorer:
    """Discovers detector-evading variants and publishes threat intel (closing the loop)."""

    def __init__(self, detector: Detector, alpha: float = 1.2, survival: float = 0.5, mutations: int = 1) -> None:
        if not (survival * mutations < 1.0):
            raise ValueError("survival * mutations must be < 1.0 to guarantee convergence")
        self.detector = detector
        self.alpha = alpha
        self.survival = survival
        self.mutations = mutations

    def _evaluate(self, v: AttackVariant) -> AttackVariant:
        # "evaded" = the detector did NOT call it malicious
        v.evaded = not self.detector.detect(Sensor.from_event(v.session)).malicious
        return v

    def _mutate(self, v: AttackVariant, tag: str) -> AttackVariant:
        # deterministic: push impact toward 1.0, preserve lineage
        return AttackVariant(
            id=f"{v.id}~{tag}", technique=v.technique, signal=v.signal, session=v.session,
            depth=v.depth, naturalness=v.naturalness, impact=min(1.0, v.impact + 0.1),
        )

    def run(self, seeds: list[AttackVariant], rounds: int = 3) -> list[AttackVariant]:
        population = [self._evaluate(s) for s in seeds]
        discovered: dict[str, AttackVariant] = {}
        for r in range(rounds):
            population.sort(key=lambda v: fitness(v, self.alpha), reverse=True)
            keep = population[: max(1, int(len(population) * self.survival))]
            for v in keep:
                if v.evaded and v.id not in discovered:
                    discovered[v.id] = v
                    # publish so Tier-2 catches this signal next time (the loop)
                    self.detector.threat_intel.add(ThreatEntry(
                        technique=v.technique, signal=v.signal,
                        guidance=f"Explorer-discovered evasion via {v.technique}", source="EAS"))
            children = [self._evaluate(self._mutate(v, f"r{r}m{m}")) for v in keep for m in range(self.mutations)]
            population = keep + children
        return list(discovered.values())
