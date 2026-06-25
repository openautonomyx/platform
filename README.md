# Agent Trust Score

A transparent **0..1** trust signal for agents. Dependency-free (Python stdlib);
reference implementation for `AGenNext/Agent-Trust-Score` (mirrors `ard/trust.py`).

Trust is **derived and explainable** — never assumed (pairs with
`No-Trust-Protocol`). A handoff or discovery decision can prefer — or require —
trustworthy agents.

## Score

`score(agent, signals)` → `TrustScore(agent, score, factors)`

| factor | weight | derived from |
| --- | --- | --- |
| identity | 0.30 | the card has an identity |
| secured | 0.20 | the card requires auth (`security`) |
| signed | 0.25 | `signals["signed"]` — e.g. Agent-Sign / cosign verified |
| governance_clean | 0.15 | `signals["governance_clean"]` (default true) |
| base | 0.10 | — |

`agent` may be an A2A card **dict** (`{"name", "security", "x-ard": {"identity": …}}`)
or any **object** with `name` / `identity` / `security`.

## Use

```python
from trust_score import score

s = score(card, signals={"signed": True})
if s.meets(0.7):
    ...  # route to / accept this agent
```

## Test

```bash
pip install pytest && pytest   # 3 tests
```
