# Service Contracts

This page defines the **interface contract** of the
[Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) service: the operations it
exposes, their inputs and outputs, and — most importantly — the **pre-conditions**,
**post-conditions**, and **invariants** each one guarantees. The contracts are written in a
language-neutral pseudo-IDL; the guarantees trace directly to the
[protocol contracts](./protocol-contracts.md) below them.

## Domain types

```text
StreamId   := string            // logical, long-lived decision stream (e.g. "decisions/credit-risk")
LedgerId   := uint64            // an individual segment within a stream
EntryId    := uint64            // position within a ledger, contiguous from 0
Offset     := (LedgerId, EntryId)
Lac        := EntryId           // last-add-confirmed watermark

DurabilityProfile := { E: uint, Qw: uint, Qa: uint, digest: CRC32C|HMAC }
                     // invariant: E >= Qw >= Qa >= 1

DecisionRecord := {
  payload      : bytes          // opaque to the service (e.g. CBOR/JSON decision envelope)
  producer     : string         // who/what appended (model id, agent id, user)
  occurred_at  : timestamp
}

Committed := {                  // returned only after Qa-durable
  offset : Offset
  lac    : Lac
}
```

## Operations

### `openStream`

```text
openStream(id: StreamId, profile: DurabilityProfile) -> StreamHandle
```

| | |
| --- | --- |
| **Pre** | `profile` satisfies `E ≥ Qw ≥ Qa ≥ 1`; caller is authorized for `id`. |
| **Post** | A `StreamHandle` bound to `id` exists; a current `OPEN` ledger is available for appends. |
| **Guarantee** | At most **one active writer** per stream is admitted (see `acquireWriter`); creating the stream is idempotent on `id`. |
| **Errors** | `Unauthorized`, `InvalidProfile`. |

### `acquireWriter`

```text
acquireWriter(id: StreamId) -> WriterLease
```

| | |
| --- | --- |
| **Pre** | Stream `id` exists. |
| **Post** | The caller holds the **exclusive** writer lease; any previous writer is fenced off at the protocol level. |
| **Guarantee** | **Single-writer**: a granted lease implies no other client can commit to the current segment. Backed by ledger [recovery + fencing](../protocol/recovery-and-fencing.md). |
| **Errors** | `WriterAlreadyActive` (lease held & live), `NotFound`. |

### `append`

```text
append(w: WriterLease, rec: DecisionRecord) -> Committed
```

| | |
| --- | --- |
| **Pre** | `w` is the current valid lease holder. |
| **Post** | `rec` is assigned the next contiguous `EntryId` and is **durably committed** before return. |
| **Guarantees** | 1) **Durability** — persisted (fsync) on `Qa` bookies before `Committed` is returned. 2) **Ordering** — assigned ids are strictly increasing with no gaps. 3) **Immutability** — the returned `offset` never changes content. |
| **On failure** | If it returns an error, the record is *not* acknowledged; it may be safely retried. A retried append that the service de-duplicates returns the original `offset` (at-least-once submit → exactly-once commit when a producer key is supplied). |
| **Errors** | `Fenced` (lease lost), `NotEnoughBookies`, `Timeout`. |

### `tail`

```text
tail(id: StreamId, from: Offset) -> Stream<DecisionRecord @ Offset>
```

| | |
| --- | --- |
| **Pre** | `from` ≤ current `LAC` + 1. |
| **Post** | Emits records in **strict id order** starting at `from`, blocking for new records as the [LAC](../protocol/last-add-confirmed.md) advances. |
| **Guarantee** | A record is delivered **only after it is committed** (≤ LAC) — never an in-flight write. This is the primitive for **decision execution** orchestration. |
| **Errors** | `OutOfRange`, `NotFound`. |

### `read`

```text
read(id: StreamId, range: [Offset, Offset]) -> List<DecisionRecord @ Offset>
```

| | |
| --- | --- |
| **Pre** | The whole range lies within sealed segments **or** ≤ current LAC. |
| **Post** | Returns the exact records in order; each is **digest-verified**. |
| **Guarantee** | **Replay determinism** — repeated reads of the same sealed range always return identical bytes (basis for reproducible audits). |
| **Errors** | `OutOfRange`, `IntegrityError` (digest mismatch). |

### `seal`

```text
seal(w: WriterLease) -> { last: Offset, length: uint64 }
```

| | |
| --- | --- |
| **Pre** | `w` is the current lease holder. |
| **Post** | The current ledger is `CLOSED` at a fixed `last` entry id and `length`; a new open ledger is started for the stream. |
| **Guarantee** | After `seal`, the sealed segment is **permanently immutable** and identical for all readers. |
| **Errors** | `Fenced`, `NotFound`. |

## Cross-cutting invariants

1. **Append-only** — no operation mutates or deletes an individual committed record; the
   unit of deletion is a whole segment under a retention policy.
2. **Single writer per stream** — enforced end-to-end via the writer lease + protocol
   fencing; eliminates write conflicts and divergent history.
3. **Committed ⇒ durable & ordered** — anything a consumer can observe (`tail`/`read`) is
   already fsync-durable on `Qa` bookies and in total order with no gaps.
4. **Sealed ⇒ frozen** — a `CLOSED` segment’s contents and length are fixed for all time
   and all readers.

## Mapping to DIP governance requirements

| DIP requirement | Contract clause that satisfies it |
| --- | --- |
| Auditable, repeatable decisions | `read` replay determinism + sealed immutability |
| Non-repudiation / no silent edits | append-only invariant + per-record digest (`IntegrityError`) |
| Reliable real-time orchestration | `tail` delivers only committed records, in order |
| Accountability (who decided what) | `DecisionRecord.producer` + immutable ordering |
