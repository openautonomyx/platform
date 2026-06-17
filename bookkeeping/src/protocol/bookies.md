# Bookies

A **bookie** is an individual BookKeeper storage server. A cluster of bookies stores the
[ledgers](./ledgers.md); crucially, **a bookie stores only fragments of ledgers**, not
whole ledgers — the [ensemble + striping](./ensembles-and-quorums.md) decides which
entries land on which bookie.

Bookies are designed to be **simple and interchangeable**: they don't talk to each other
to serve writes or reads. The client (writer) coordinates replication directly, and the
metadata store tracks membership. This keeps bookies horizontally scalable.

## Membership

Each bookie registers itself in the metadata store (an ephemeral znode in ZooKeeper).
Writers discover available bookies there when choosing an ensemble or performing an
[ensemble change](./ensembles-and-quorums.md#ensemble-changes); when a bookie dies, its
ephemeral registration disappears.

## The two storage paths

A bookie separates the **write path** (optimized for low-latency sequential durability)
from the **read path** (optimized for locality), which is the key to BookKeeper's
performance.

```text
   addEntry ─► ┌──────────────────┐  fsync   ack
               │     Journal       │ ───────► (durable!)   ◄── write path: sequential WAL
               └────────┬─────────┘
                        │ async
                        ▼
               ┌──────────────────┐
               │  Ledger storage   │   entry log(s) + index   ◄── read path
               │  (entry log +     │   (ledgerId,entryId) →
               │   index/RocksDB)  │   (entryLogId, offset)
               └──────────────────┘
```

### Journal (write-ahead log)

The **journal** is an append-only write-ahead log on the bookie. Every `addEntry` is
appended to the journal and **forced to stable storage (fsync)** *before* the bookie
acknowledges the write. This is the heart of BookKeeper's durability: an acknowledged
entry has survived an fsync on `Qa` bookies, so it persists across process and machine
crashes. Because the journal is purely sequential, these durable writes are fast.

### Ledger storage (entry log + index)

For reads, entries from *many* ledgers are interleaved and appended into **entry log**
files, and an **index** maps `(ledgerId, entryId) → (entryLogId, offset)`. Two common
implementations:

- **DbLedgerStorage** — index kept in RocksDB; the modern default for large clusters.
- **InterleavedLedgerStorage** — per-ledger index files with a ledger cache.

Writing the entry log asynchronously (after the journal has already made the write
durable) lets the read path be organized for locality without slowing the commit path.

## Why this matters for the service

[Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) inherits a clean operational
story from this design:

- **Durability is explicit** — an acked decision record is fsync'd on `Qa` bookies.
- **Bookies are cattle** — a failed bookie is replaced by an
  [ensemble change](./ensembles-and-quorums.md#ensemble-changes); under-replicated
  fragments are re-replicated by the auto-recovery process.
- **Write and read scale independently** — append latency depends on the journal; read
  throughput depends on ledger storage and the spread of the ensemble.
