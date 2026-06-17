# Ensembles & Quorums

Replication in BookKeeper is governed by three numbers chosen per ledger:

| Symbol | Name | Meaning |
| --- | --- | --- |
| **`E`** | Ensemble size | The number of [bookies](./bookies.md) across which the ledger's entries are spread. |
| **`Qw`** | Write quorum | The number of bookies **each entry** is written to (its replication factor). |
| **`Qa`** | Ack quorum | The number of acknowledgements the writer must receive before treating the entry as committed. |

They must satisfy:

```text
E ≥ Qw ≥ Qa ≥ 1
```

- `Qw` controls how many copies of each entry exist (read availability & durability).
- `Qa` controls how many copies must be confirmed before acking (write latency vs. safety).
- `E` controls how widely load is spread (throughput); when `E > Qw` the ledger is
  **striped**.

## The ensemble

The **ensemble** is the (ordered) list of bookies that store a ledger's content. It is
recorded in the ledger [metadata](./ledgers.md#metadata). Because the list is ordered,
"the bookie at index *i*" is well defined — which is what makes striping deterministic.

## Striping

Entries are **striped** across the ensemble: entry *e* is written to the `Qw` consecutive
bookies of the ensemble starting at index `e mod E` (wrapping around the end). The set of
bookies an entry is written to is its **write quorum**, and the **ack quorum** is any
`Qa`-sized subset of that write quorum.

Example with `E=5, Qw=3, Qa=2` (`B0..B4` are the ensemble bookies; `✓` = entry stored
there):

```text
            B0    B1    B2    B3    B4     write quorum (start = e mod 5)
 entry e0   ✓     ✓     ✓                  {B0,B1,B2}
 entry e1         ✓     ✓     ✓            {B1,B2,B3}
 entry e2               ✓     ✓     ✓      {B2,B3,B4}
 entry e3   ✓                 ✓     ✓      {B3,B4,B0}
 entry e4   ✓     ✓                 ✓      {B4,B0,B1}
 entry e5   ✓     ✓     ✓                  {B0,B1,B2}  (cycle repeats)
```

Benefits:

- **Throughput** — consecutive entries hit different bookies, so writes (and reads) are
  parallelized across the cluster instead of bottlenecking on one disk.
- **Balanced load** — over many entries, each ensemble bookie receives a roughly equal
  share.

When `Qw = E`, every entry is written to every bookie (no striping — pure mirroring).

## Ack quorum and fault tolerance

The writer sends each entry to all `Qw` bookies in its write quorum but only waits for the
fastest `Qa` to acknowledge. Consequences:

- **Latency** is bounded by the `Qa`-th fastest bookie, not the slowest — a slow/straggler
  bookie doesn't stall commits.
- An acknowledged entry survives the loss of up to **`Qa − 1`** bookies without data loss.
- An entry remains **readable** as long as at least one of its `Qw` copies is reachable,
  i.e. it tolerates up to **`Qw − 1`** failures for read availability.

## Ensemble changes

If a bookie in the ensemble fails *while the writer is writing*, the writer doesn't stall:
it selects a replacement bookie from the available pool and records a **new ensemble
fragment** in the ledger metadata, keyed by the entry id at which the change takes effect.

```text
metadata fragments for ledger 42:
  entry 0   → [B0, B1, B2, B3, B4]
  entry 97  → [B0, B1, B5, B3, B4]   ← B2 failed; replaced by B5 from entry 97 on
```

A reader locating entry *e* first finds the fragment whose range covers *e*, then applies
striping within that fragment's ensemble. Separately, an **auto-recovery / re-replication**
process detects under-replicated fragments (e.g. after a permanent bookie loss) and copies
entries to fresh bookies to restore the `Qw` replica count.

## Choosing `E`/`Qw`/`Qa` for a decision stream

[Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) lets each decision stream pick
its profile:

| Profile | `E` | `Qw` | `Qa` | Trade-off |
| --- | --- | --- | --- | --- |
| High-durability audit | 5 | 3 | 3 | Strongest safety; commit waits for all 3 copies. |
| Balanced (default) | 3 | 3 | 2 | One bookie may lag/fail without blocking commits. |
| High-throughput ingest | 8 | 3 | 2 | Wide striping for throughput; 3 copies per entry. |
