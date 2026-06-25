# Agent Handoff Protocol (v0.1)

Reference implementation: [`ard/handoff.py`](ard/handoff.py) + [`ard/trust.py`](ard/trust.py).
For `AGenNext/Agent-Handoff-Protocol` and `AGenNext/Agent-Trust-Score`.

One agent **delegates a task to another** across the AgentWorld mesh, with
identity and trust.

## Flow

```
discover → prepare → transmit → verify → accept/reject → record
```

1. **discover** — the broker finds an agent offering the needed `skill` via the
   registry / federation; with a trust scorer it picks the **highest-trust**
   target and can require a `min_trust` floor.
2. **prepare** — build a `HandoffRequest` envelope; the source is appended to
   `trace`.
3. **transmit** — POST the envelope to the target (A2A transport, out of band).
4. **verify** — the receiver checks `token` against the expected identity
   (AuthX-ID) and may re-check the source's trust score.
5. **accept / reject** — the receiver returns a `HandoffReceipt`.
6. **record** — every step is emitted to the governance sink (→ agx).

## Envelope — `HandoffRequest`

| field | meaning |
| --- | --- |
| `version` | protocol version (`0.1`) |
| `id` | unique handoff id |
| `from` / `to` | source / target agent names |
| `skill` | the skill being delegated |
| `task` | the work payload |
| `context` | shared context carried with the task |
| `reason` | why the handoff happens |
| `token` | identity token authenticating the source (AuthX-ID) |
| `trace` | prior agent hops — multi-hop chains stay auditable |
| `mediaType` | `application/vnd.agentworld.handoff+json` |

## Trust (Agent-Trust-Score)

`score_card(card, signals)` → a transparent **0..1** score from explainable
factors: identity present, auth required, **signed** artifact (Agent-Sign), clean
governance. Brokers rank candidate targets by score and enforce `min_trust`.

## Example

```python
from ard import Registry, agent_card, HandoffBroker, score_card

reg = Registry()
reg.register(agent_card("refunder", "Refunds", "http://r", kind="tool", skills=["refund"]))

broker = HandoffBroker(discover=reg.query, trust=score_card)
req = broker.prepare(from_agent="orchestrator", skill="refund", task={"amount": 50}, min_trust=0.2)
# → HandoffRequest targeting "refunder", recorded for governance
```
