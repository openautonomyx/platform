# agx-ADR — Agentic Detection & Response (reference sketch)

A dependency-free sketch of the **ADR** architecture (arXiv 2605.17380, *"ADR:
An Agentic Detection System for Enterprise Agentic AI Security"*) for the
**agx** security plane. It sits on top of **Agent-Discovery (ard)**: ard's MCP
registry says what tools exist and do (Tier-2 context); ard's governance feed is
the Sensor's input.

## Components

- **Sensor** — normalize telemetry into a causal chain
  (`prompt → reasoning → tool calls → outcome + env`). `Sensor.from_event(event)`.
- **Detector** — two-tier, **precision-first**:
  - **Tier 1** `triage()` — fast, high-recall heuristics (secret patterns +
    entropy, prompt-injection phrases, sensitive-path access, access→exfil
    combos). Clearly-benign sessions short-circuit.
  - **Tier 2** reasoning — context-aware verdict via a pluggable `reasoner`
    (LLM) plus `threat_intel` / `policy` providers. A sensitive read *alone*
    escalates to a human rather than auto-flagging (keeps false positives low).
- **Explorer** — offline evolutionary red-teaming. Fitness `F = ε·σ·τ^α`
  (α = 1.2); converges when `survival·mutations < 1`. Evading variants are
  published as threat intel back into the Detector — **closing the loop**.

## Use

```python
from agx_adr import Sensor, Detector

v = Detector().detect(Sensor.from_event(event))   # event from ard's governance feed
if v.malicious:
    alert(v)                                       # tactic, confidence, rationale, tier
```

## Place in the ecosystem

- **consumes** `ard` (Agent-Discovery): `ard mcp-registry` for tool semantics +
  the governance feed for sessions.
- **belongs to** `agx` (identity · governance · auth · security), alongside
  `No-Trust-Protocol`, `Agent-Sentinel`, `Agent-Sign`.
- **benchmark target:** ADR-Bench (5 tactics / 17 techniques).

## Test

```bash
pip install pytest && pytest   # 8 tests
```

> This is a **sketch**: triage/reasoning are deterministic rules so it runs
> offline. In production, Tier-2 swaps in an LLM `reasoner` and live MCP context
> providers (source-code / threat-intel / policy), exactly as in the paper.
