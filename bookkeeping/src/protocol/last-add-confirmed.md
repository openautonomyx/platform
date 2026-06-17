# Last-Add-Confirmed & Reads

**Last-Add-Confirmed (`LAC`)** is the consistency boundary of an open ledger. It is the id
of the highest entry that has been acknowledged by at least `Qa` bookies — and, because
entries commit in order, *every* entry up to and including the LAC is durably committed and
safe to read.

```text
 committed & readable          in flight (not yet Qa-acked)
 ┌────┬────┬────┬────┐  │  ┌────┬────┐
 │ e0 │ e1 │ e2 │ e3 │  │  │ e4 │ e5 │
 └────┴────┴────┴────┘  │  └────┴────┘
                  ▲
                 LAC = 3
```

## Why a boundary is needed

While a ledger is `OPEN`, the writer is racing ahead: it may have *sent* entries `e4` and
`e5` to bookies but not yet collected `Qa` acks. Those entries are **not yet committed** —
a writer crash could leave them partially written. If a reader were allowed to return `e4`
before it was confirmed, two readers could disagree about whether `e4` exists. The `LAC`
prevents this: **regular readers may only read entries with id ≤ LAC**, so everyone sees
the same committed prefix.

## How readers learn the LAC

1. **Piggybacking** — every [entry](./entries.md) carries the writer's `last confirmed`
   value at the time it was written. A reader streaming the log therefore advances its view
   of the LAC for free as it reads.
2. **Explicit `readLac`** — a reader can ask bookies directly for the current LAC.
3. **Long-poll read (`readLastAddConfirmedAndEntry`)** — a reader can block until the LAC
   advances past a given entry and receive the new entry in the same round trip. This is
   the low-latency **tailing** primitive: consumers follow the log as it grows without busy
   polling.

## Reads in BookKeeper

- **Bounded read** — read a specific range `[from, to]`. For an open ledger, `to` must be
  ≤ LAC; for a `CLOSED` ledger, the whole `[0, lastEntryId]` range is readable.
- **Tailing read** — follow the LAC via long-poll to consume new entries as they commit.
- A read for entry *e* is served by contacting the bookies in *e*'s write quorum (computed
  from the covering [fragment's ensemble](./ensembles-and-quorums.md#ensemble-changes) and
  the striping rule); the first valid, digest-verified copy wins, so a single reachable
  replica is enough.

## Mapping to the service

[Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md) surfaces the LAC as the
"safe-to-consume" watermark of a decision stream:

- **Decision execution** consumers *tail* up to the LAC, so a downstream step only ever
  fires on a decision record that is already durable — never on an in-flight write that
  might vanish.
- **Decision governance / audit** replays operate over `CLOSED` ledgers, where the full
  range is fixed and immutable, guaranteeing every auditor sees the identical history.
