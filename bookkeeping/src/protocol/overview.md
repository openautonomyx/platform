# Protocol Overview

Apache BookKeeper provides **highly available, durable logs**. The protocol is built
around a small number of concepts that compose into strong guarantees. This part of the
book walks through each one; this page is the map.

## The data model in one paragraph

A **ledger** is an ordered, append-only sequence of **entries**. Each entry is replicated
across a set of storage servers — **bookies** — chosen for that ledger (its **ensemble**).
A ledger has a single writer at a time. The writer appends entries; each entry is written
to **write-quorum** (`Qw`) bookies, and once **ack-quorum** (`Qa`) of them confirm, the
entry is considered durably committed and the **Last-Add-Confirmed** (`LAC`) pointer
advances. Ledger **metadata** — the ensemble, quorum sizes, state, and (once closed) the
final length — lives in a metadata store such as ZooKeeper.

```text
ledger 42 (OPEN, E=3, Qw=2, Qa=2)
 ┌──────┬──────┬──────┬──────┬──────┬──────┐
 │ e0   │ e1   │ e2   │ e3   │ e4   │ e5   │  ← entries, strictly ordered
 └──────┴──────┴──────┴──────┴──────┴──────┘
                          ▲
                          └── LAC = 3  (e0..e3 are committed & readable;
                                          e4, e5 are in flight)
```

## The three core operations

The protocol exposes three fundamental operations (plus open/recover and close, covered
later):

1. **Create a ledger** — allocate a ledger id, choose an ensemble of bookies, and record
   metadata (`E`, `Qw`, `Qa`, digest type, state = `OPEN`).
2. **Add an entry** — append a record to a ledger. The writer stripes it across the
   appropriate `Qw` bookies and waits for `Qa` acknowledgements.
3. **Read entries** — fetch a range of entries from the bookies that hold them. Regular
   readers may read up to the `LAC`.

## Reading order

| Page | Concept |
| --- | --- |
| [Entries](./entries.md) | The atomic record and its fields |
| [Ledgers](./ledgers.md) | The append-only sequence and its lifecycle |
| [Bookies](./bookies.md) | The storage servers; journal vs. ledger storage |
| [Ensembles & Quorums](./ensembles-and-quorums.md) | Replication, striping, `E`/`Qw`/`Qa` |
| [Last-Add-Confirmed & Reads](./last-add-confirmed.md) | The consistency boundary |
| [Closing, Recovery & Fencing](./recovery-and-fencing.md) | Single agreed history |
| [Guarantees](./guarantees.md) | What it all adds up to |

## Roles

- **Writer (client)** — the single client appending to a ledger; also drives create,
  close, ensemble changes, and (when it is a recovering client) recovery.
- **Reader (client)** — any client reading entries up to the LAC, or all entries of a
  closed ledger.
- **Bookie** — a storage server that persists and serves entries.
- **Metadata store** — ZooKeeper/etcd; holds ledger metadata and the live bookie set.
