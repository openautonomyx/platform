# Agent Handoff Protocol (v0.1)

One agent **delegates a task to another** across the AgentWorld mesh, with
identity and trust. Dependency-free (Python stdlib); reference implementation
for `AGenNext/Agent-Handoff-Protocol` (mirrors `ard/handoff.py`).

## Flow

```
discover → prepare → transmit → verify → accept/reject → record
```

1. **discover** — the broker finds an agent offering the needed `skill` (via any
   `discover(skill, kind)` callable — e.g. a registry/federation). With a trust
   scorer it picks the **highest-trust** target and can require `min_trust`.
2. **prepare** — build a `HandoffRequest`; the source is appended to `trace`.
3. **transmit** — POST the envelope to the target (out of band).
4. **verify** — the receiver checks the `token`'s issuer/audience (identity).
5. **accept / reject** — the receiver returns a `HandoffReceipt`.
6. **record** — every step is emitted to a governance sink.

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
| `token` | identity token authenticating the source |
| `trace` | prior agent hops — multi-hop chains stay auditable |
| `mediaType` | `application/vnd.agentworld.handoff+json` |

Pairs with **Agent-Trust-Score** (rank/gate targets) and identity (`token`
verification). Receiver verifies via `HandoffBroker.verify(req, issuer, audience)`.

## Use

```python
from handoff_protocol import HandoffBroker

broker = HandoffBroker(discover=registry_query, trust=trust_scorer)
req = broker.prepare(from_agent="orchestrator", skill="refund",
                     task={"amount": 50}, min_trust=0.7)
# → HandoffRequest targeting the most-trusted "refund" agent, recorded for governance
```

## Test

```bash
pip install pytest && pytest   # 5 tests
```
