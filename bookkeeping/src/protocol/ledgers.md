# Ledgers

A **ledger** is the basic building block of BookKeeper: an **ordered, append-only sequence
of [entries](./entries.md)** with a **single writer**. Ledgers are the unit of
replication, of lifecycle, and of deletion.

## Properties

- **Ordered** — entries have monotonically increasing ids and a total order.
- **Append-only** — you can only add to the tail; existing entries are immutable.
- **Single-writer** — exactly one client writes a given ledger over its lifetime. This is
  what makes the order unambiguous and gap-free.
- **Written at most once** — each entry id is assigned once; combined with
  [recovery + fencing](./recovery-and-fencing.md), all clients agree on the contents.

## Lifecycle

A ledger moves through three states, recorded in its metadata:

```text
            create                 writer crash / takeover
   (none) ─────────► OPEN ───────────────────────────────► IN_RECOVERY
                       │                                          │
                       │ writer closes cleanly                    │ recovery completes
                       ▼                                          ▼
                    CLOSED ◄───────────────────────────────── CLOSED
```

| State | Meaning |
| --- | --- |
| **OPEN** | The writer is appending. The tail (last entry id) is not yet fixed in metadata; readers track progress via the [LAC](./last-add-confirmed.md). |
| **IN_RECOVERY** | A client (not the original writer) is recovering the ledger after a suspected writer failure. The ledger is [fenced](./recovery-and-fencing.md) so the old writer can make no further progress. |
| **CLOSED** | The last entry id and the ledger length are fixed in metadata. The ledger is now fully immutable; all readers see identical contents. |

## Metadata

Each ledger has metadata stored in the metadata service (ZooKeeper/etcd), including:

- the **ensemble(s)** — the bookies holding the ledger, as an ordered list of *fragments*
  (each fragment is `firstEntryId → [bookies]`, supporting
  [ensemble changes](./ensembles-and-quorums.md#ensemble-changes));
- **`Qw`** (write quorum) and **`Qa`** (ack quorum);
- the **digest type** and (for HMAC) the ledger password;
- the **state** (`OPEN`/`IN_RECOVERY`/`CLOSED`);
- once closed, the **last entry id** and **length**.

## Fragments

A ledger is not necessarily stored on one fixed set of bookies for its whole life. If a
bookie fails mid-write, the writer performs an **ensemble change** and starts a new
*fragment* from the next entry id. Thus a ledger's metadata is an ordered list of
fragments; to locate entry *e*, a reader finds the fragment whose range covers *e* and
then computes the [striping](./ensembles-and-quorums.md#striping) within that fragment's
ensemble.

## Relationship to streams in the service

The [Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) service exposes long-lived
**decision streams**. Under the hood a stream is a *sequence of ledgers*: the service
appends to the current open ledger, seals it (closes it) on rollover or on writer change,
and starts a new one — giving unbounded, immutable history composed of finite,
individually-recoverable ledgers.
