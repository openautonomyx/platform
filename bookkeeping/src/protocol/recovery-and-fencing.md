# Closing, Recovery & Fencing

A ledger has a single writer — but what happens when that writer **crashes** without
cleanly closing the ledger? BookKeeper's answer is **recovery** protected by **fencing**,
and it is what guarantees that *all clients eventually agree on one history*, even with no
cooperation from the (possibly dead, possibly merely partitioned) original writer.

## Closing cleanly

When a writer finishes normally, it **closes** the ledger: it records the **last entry id**
and the **ledger length** into the metadata and sets the state to `CLOSED`. From that
moment the ledger is fully immutable and every reader sees identical contents over the full
range `[0, lastEntryId]`.

## The problem: an unclosed ledger

If the writer dies while the ledger is still `OPEN`, the metadata has **no recorded last
entry id**. Around the tail, some entries may have reached `Qa` bookies (committed) and
some may have reached only a few or none (uncommitted). A new client that wants to use the
ledger must decide, definitively, *where the ledger ends* — and must stop the old writer
from adding anything after that point.

## Recovery

A client opens the ledger **in recovery mode**, performing roughly these steps:

```text
1. Set metadata state OPEN → IN_RECOVERY.
2. Send a FENCE request (combined with reads) to the bookies of the last ensemble.
3. Once a quorum is fenced, find the last recoverable entry: read from the ensemble to
   determine the highest entry that is (or can be made) present on Qa bookies.
4. Re-replicate any tail entries that are under-replicated so every entry up to that
   point satisfies Qw / Qa.
5. Close the ledger: write lastEntryId + length to metadata, state IN_RECOVERY → CLOSED.
```

After recovery, the ledger is `CLOSED` at a well-defined last entry id, and the history is
fixed for everyone.

## Fencing

**Fencing** is the safety mechanism that makes recovery correct. When the recovering client
contacts the bookies, it marks the ledger as **fenced** on them. A fenced bookie will
**reject any further `addEntry` from the original writer** for that ledger (the write fails
with a *ledger fenced* error).

```text
        old writer (zombie)                 recovering client
              │  addEntry(e) ──► bookie ◄── FENCE ledger 42 ──┘
              │                    │
              └──────  ✗ rejected ─┘   (LedgerFencedException)
```

Why it's essential: without fencing, a writer that was only *temporarily* partitioned
(not actually dead) could come back and keep appending entries *after* the recovering
client had already decided where the ledger ends — producing two divergent histories
(**split-brain**). Fencing guarantees that **once recovery begins, the old writer can never
make further progress**, so there is exactly one agreed-upon tail.

> Because any bookie in the write quorum that is fenced will reject the old writer, the old
> writer can no longer assemble an ack quorum — so it cannot commit new entries.

## Why this matters for the service

This is the property that lets [Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md)
promise a **single, non-repudiable history of decisions**:

- If the component writing a decision stream crashes, another instance recovers and seals
  the ledger at a definite point — no decision record is ever "maybe there, maybe not."
- A delayed or partitioned old writer cannot resurrect and inject extra decision records
  after the fact; fencing forecloses that, which is exactly the guarantee an audit/
  governance trail requires.
