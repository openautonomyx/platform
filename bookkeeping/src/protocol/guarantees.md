# Guarantees

Everything in the previous pages composes into a small set of guarantees. These are the
promises the [Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) service inherits
and re-exposes; the formal versions are in [Protocol Contracts](../contracts/protocol-contracts.md).

## Durability

An entry that has been **acknowledged** to the writer has been written and **fsync'd to the
[journal](./bookies.md#journal-write-ahead-log)** of at least `Qa`
[bookies](./bookies.md). Therefore:

> An acknowledged entry is **not lost** as long as no more than **`Qa − 1`** of its bookies
> fail simultaneously.

Durability is a *commit-time* property — it holds the instant the writer receives the ack,
because the data is already on stable storage.

## Ordering

> Within a ledger, entries are **totally ordered** by entry id, and the committed prefix
> (everything ≤ [LAC](./last-add-confirmed.md)) has **no gaps**.

The single-writer model assigns ids sequentially; commit advances the LAC only in order.

## Consistency (single agreed history)

> All clients that read a `CLOSED` ledger see **identical contents and length**; readers of
> an `OPEN` ledger see a **consistent committed prefix** bounded by the LAC.

This holds even across writer crashes, because [recovery + fencing](./recovery-and-fencing.md)
fix a single last entry id and prevent any divergent continuation (no split-brain).

## Availability

> A confirmed entry remains **readable** while at least one of its `Qw` copies is reachable
> (tolerates up to `Qw − 1` failures); a writer can **keep writing** despite bookie
> failures by performing an [ensemble change](./ensembles-and-quorums.md#ensemble-changes).

Write availability is preserved as long as enough bookies exist in the cluster to assemble
a fresh write quorum.

## Integrity

> Every entry carries a [digest](./entries.md#digest--authentication); a reader verifies it,
> so corruption (on disk or in transit) and tampering are **detectable**.

## The trade-off knobs

| You want… | Tune… |
| --- | --- |
| Stronger durability per entry | higher `Qa` |
| Lower commit latency | lower `Qa` (relative to `Qw`) |
| More read replicas / read availability | higher `Qw` |
| Higher throughput | larger `E` (wider striping) |

## Summary table

| Guarantee | Holds because… | Tolerates |
| --- | --- | --- |
| Durability | journal fsync on `Qa` bookies before ack | `Qa − 1` bookie failures (no loss) |
| Read availability | `Qw` replicas per entry | `Qw − 1` failures (still readable) |
| Ordering / no gaps | single writer + in-order LAC | — |
| Single history | recovery + fencing | writer crash, partition (no split-brain) |
| Integrity | per-entry digest | corruption / tampering (detectable) |
