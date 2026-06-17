# Service: Autonomyx BookKeeping

> **Catalog entry — Decision Service**

| Field | Value |
| --- | --- |
| **Service name** | Autonomyx BookKeeping |
| **Category** | Platform / Decision Governance & Execution |
| **Type** | Decision service (componentized, reusable, discoverable) |
| **Powered by** | [Apache BookKeeper](./tool-apache-bookkeeper.md) (tool) |
| **Interface** | See [Service Contracts](./contracts/service-contracts.md) |
| **Status** | Proposed |

## Summary

**Autonomyx BookKeeping** is the platform's **system of record for decisions**. It
exposes a durable, append-only, strictly-ordered **ledger** as a managed service, so any
decision flow, model, or agent on the Autonomyx DIP can record what it did — and replay
it later — with strong durability and ordering guarantees, without owning the underlying
storage machinery.

It maps onto two of the DIP's mandatory features:

- **Decision governance** — every decision becomes an immutable, auditable ledger entry:
  who/what decided, on which inputs, using which model version, with what output, and the
  eventual outcome. Entries can be read back in exact order for audit, replay, lineage,
  and dispute resolution.
- **Decision execution** — the same ledger is the reliable backbone for orchestrating
  decision flows in batch and real time. Producers append; consumers tail the log to
  drive downstream steps, exactly once and in order.

## Where it fits in the platform

```text
                ┌─────────────────────────────────────────────┐
                │            Autonomyx DIP                      │
                │                                               │
  Decision      │   Decision        Decision        Decision   │
  modeling ───► │   execution  ───► monitoring ───► governance │
                │      │               ▲               ▲        │
                │      │ append        │ tail/replay   │ audit  │
                │      ▼               │               │        │
                │   ┌───────────────────────────────────────┐  │
                │   │      Autonomyx BookKeeping (service)   │  │
                │   └───────────────────┬───────────────────┘  │
                └───────────────────────┼──────────────────────┘
                                        │ ledgers / entries
                                        ▼
                            ┌───────────────────────┐
                            │  Apache BookKeeper     │  (tool)
                            │  bookies + metadata    │
                            └───────────────────────┘
```

## Core capabilities

1. **Append decision records** — write an entry to a named decision stream; the service
   assigns a monotonically increasing entry id and durably replicates it.
2. **Tail in real time** — consumers follow a stream from any position up to the
   [Last-Add-Confirmed](./protocol/last-add-confirmed.md) boundary for execution
   orchestration.
3. **Replay / audit** — read any closed range of a stream back in exact order for
   governance, lineage, and reproducibility.
4. **Seal** — close a stream segment to make it permanently immutable.
5. **Survive failure** — automatic replication, recovery, and
   [fencing](./protocol/recovery-and-fencing.md) guarantee a single agreed history even
   across writer crashes.

## Design principles inherited from the tool

- **Append-only & immutable** — entries are never updated in place; corrections are new
  entries. This is what makes the audit trail trustworthy.
- **Single-writer per segment** — each ledger has exactly one writer, eliminating
  write conflicts and giving a clean, gap-free order.
- **Tunable durability** — each decision stream chooses its ensemble size, write quorum,
  and ack quorum to trade latency against fault tolerance (see
  [Ensembles & Quorums](./protocol/ensembles-and-quorums.md)).

## Service Level Objectives (proposed)

| SLO | Target |
| --- | --- |
| Durability of an acknowledged entry | No loss while ≤ `Qa − 1` bookies fail simultaneously |
| Read availability of a confirmed entry | Available while ≤ `Qw − 1` of its bookies fail |
| Ordering | Total order within a decision stream; no gaps below LAC |
| Append latency (p99) | Bounded by slowest of the `Qa` fastest bookies + journal fsync |

The exact operations, inputs, outputs, and guarantees are specified in
[Service Contracts](./contracts/service-contracts.md).
