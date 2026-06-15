# Tool: Apache BookKeeper

> **Catalog entry — Tool / Open-source component**

| Field | Value |
| --- | --- |
| **Tool name** | Apache BookKeeper |
| **Vendor / project** | The Apache Software Foundation |
| **License** | Apache License 2.0 |
| **Category** | Distributed write-ahead log / replicated log storage |
| **Home** | <https://bookkeeper.apache.org/> |
| **Protocol docs** | <https://bookkeeper.apache.org/docs/development/protocol> |
| **Used by** | [Autonomyx BookKeeping](./service-autonomyx-bookkeeping.md) (service) |

## What it is

**Apache BookKeeper** is a scalable, fault-tolerant, low-latency storage service
optimized for **append-only** workloads. It stores sequences of records called
**[entries](./protocol/entries.md)** in logs called **[ledgers](./protocol/ledgers.md)**,
replicated across storage servers called **[bookies](./protocol/bookies.md)**.

It was designed with **write-ahead logging** in mind: the core operation is "append a
record and don't lose it," with strong **durability**, strict **ordering**, and a clear
**consistency** boundary. It is the storage engine behind systems such as Apache Pulsar,
Apache DistributedLog, and Pravega, and is widely used to store transaction logs,
message streams, consumer offsets, and replicated metadata.

## Why we selected it for the service

| Requirement of Autonomyx BookKeeping | What BookKeeper provides |
| --- | --- |
| Never lose an acknowledged decision record | Journaled (fsync'd) writes replicated to an **ack quorum** |
| Strict, gap-free ordering for replay | Sequential entry ids within a ledger; single-writer model |
| A clear "safe to read" boundary | **[Last-Add-Confirmed](./protocol/last-add-confirmed.md)** (LAC) |
| One agreed history even after a crash | **[Recovery + fencing](./protocol/recovery-and-fencing.md)** |
| Scale throughput horizontally | **[Striping](./protocol/ensembles-and-quorums.md)** across an ensemble |
| Tunable cost/latency/durability | Independent **ensemble**, **write quorum**, **ack quorum** |

## Key building blocks (at a glance)

- **Entry** — a single record: ledger id, entry id, last-confirmed, payload, and an
  authentication digest. See [Entries](./protocol/entries.md).
- **Ledger** — an ordered, append-only, single-writer sequence of entries with a
  lifecycle of `OPEN → IN_RECOVERY → CLOSED`. See [Ledgers](./protocol/ledgers.md).
- **Bookie** — an individual storage server holding fragments of ledgers, with a
  **journal** (write path) and **ledger storage** (read path). See
  [Bookies](./protocol/bookies.md).
- **Metadata store** — ZooKeeper (or etcd) holds ledger metadata and bookie membership.
- **Ensemble / Qw / Qa** — how entries are replicated and striped. See
  [Ensembles & Quorums](./protocol/ensembles-and-quorums.md).

## Operational shape

```text
   Client (writer)                         Metadata store (ZooKeeper/etcd)
        │  create ledger ────────────────────────►  ledger metadata
        │                                            (ensemble, Qw, Qa, state)
        │  addEntry(e) ──► striped to Qw bookies
        ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ bookie1 │   │ bookie2 │   │ bookie3 │   │ bookie4 │   ... ensemble of E bookies
   │ journal │   │ journal │   │ journal │   │ journal │   (each ack after fsync)
   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

The remainder of this book — the **Protocol** and **Contracts** parts — explains exactly
how these pieces behave and what they promise.
