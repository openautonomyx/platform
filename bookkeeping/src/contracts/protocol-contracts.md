# Protocol Contracts

These are the formal contracts of the underlying **Apache BookKeeper** operations that the
[service contracts](./service-contracts.md) build upon. Each operation is specified with
its **pre-conditions**, **post-conditions**, **invariants**, and **error conditions**.

## State & symbols

```text
E, Qw, Qa : ensemble size, write quorum, ack quorum   (invariant: E >= Qw >= Qa >= 1)
ensembleOf(ledger, e) : the Qw bookies for entry e
                        = Qw consecutive bookies of the covering fragment's ensemble,
                          starting at index (e mod E)        // striping
state(ledger) ∈ { OPEN, IN_RECOVERY, CLOSED }
LAC(ledger)   : highest entry id acknowledged by >= Qa bookies (and all before it)
```

Global invariants that every operation must preserve:

- **I1 — Ordering:** entry ids within a ledger are assigned strictly increasing, starting
  at 0, with no gaps at or below `LAC`.
- **I2 — Immutability:** once an entry id is committed, its bytes never change.
- **I3 — Single writer:** at most one client can successfully add entries to a ledger at a
  time; a fenced ledger admits no further adds from the fenced writer.
- **I4 — Durable prefix:** every entry `e ≤ LAC` is present (fsync’d) on at least `Qa`
  bookies of `ensembleOf(ledger, e)`.

## `createLedger`

```text
createLedger(E, Qw, Qa, digest) -> ledgerId
```

| | |
| --- | --- |
| **Pre** | `E ≥ Qw ≥ Qa ≥ 1`; at least `E` bookies are available. |
| **Post** | A fresh `ledgerId` exists; metadata records the ensemble, `E/Qw/Qa`, `digest`, `state = OPEN`; the caller is its sole writer. |
| **Errors** | `NotEnoughBookies`, `InvalidQuorum`, `MetadataError`. |

## `addEntry`

```text
addEntry(ledgerId, data) -> entryId        // writer-only
```

| | |
| --- | --- |
| **Pre** | `state(ledgerId) = OPEN`; caller is the writer; ledger not fenced against caller. |
| **Action** | Assign next `entryId`; stamp the entry with current `LAC` and `digest`; send to all bookies in `ensembleOf(ledgerId, entryId)`; await `Qa` acks. |
| **Post (success)** | The entry is on `≥ Qa` bookies’ journals (fsync’d). When this entry and all prior are confirmed, `LAC` advances to (at least) `entryId`. Preserves **I1, I2, I4**. |
| **Post (failure)** | The entry is **not** acknowledged; `LAC` does not advance past it. The writer may retry or perform an [ensemble change](../protocol/ensembles-and-quorums.md#ensemble-changes). |
| **Errors** | `LedgerFenced` (→ another client is recovering; caller must stop — **I3**), `LedgerClosed`, `NotEnoughBookies`, `Timeout`. |

## `readEntries`

```text
readEntries(ledgerId, from, to) -> [entry]
```

| | |
| --- | --- |
| **Pre** | If `state = OPEN`: `to ≤ LAC`. If `state = CLOSED`: `to ≤ lastEntryId`. |
| **Action** | For each `e ∈ [from,to]`, contact bookies of `ensembleOf(ledgerId, e)`; return the first digest-valid copy. |
| **Post** | Returns exactly the requested entries, in order; each is digest-verified. Read-only — preserves all invariants. |
| **Guarantee** | Succeeds while ≥ 1 of each entry’s `Qw` copies is reachable (tolerates `Qw − 1` failures). |
| **Errors** | `NoSuchEntry`, `NoSuchLedger`, `Unreadable> (all copies unreachable)`, `DigestMismatch`. |

## `readLac` / long-poll

```text
readLac(ledgerId) -> lac
readLastAddConfirmedAndEntry(ledgerId, prevEntryId, timeout) -> (lac, entry?)
```

| | |
| --- | --- |
| **Pre** | Ledger exists. |
| **Post** | Returns the current `LAC` (a lower bound on the durable prefix). The long-poll variant blocks until `LAC > prevEntryId` or `timeout`, returning the next entry when it commits. |
| **Guarantee** | The returned `lac` only ever **increases** over time for a given ledger (monotonic). |

## `closeLedger`

```text
closeLedger(ledgerId) -> (lastEntryId, length)     // writer-only, clean close
```

| | |
| --- | --- |
| **Pre** | Caller is the writer; `state = OPEN`. |
| **Post** | Metadata records `lastEntryId` and `length`; `state = CLOSED`. The ledger is now immutable; **I2** holds over `[0, lastEntryId]` for all readers. |
| **Errors** | `LedgerFenced`, `MetadataError`. |

## `openAndRecover` (fencing recovery)

```text
openAndRecover(ledgerId) -> (lastEntryId, length)   // any client, after writer crash
```

| | |
| --- | --- |
| **Pre** | Ledger exists in state `OPEN`. |
| **Action** | 1) set `state = IN_RECOVERY`; 2) **fence** the last ensemble (bookies reject further adds from the old writer — enforces **I3**); 3) determine the highest recoverable entry by reading the ensemble; 4) re-replicate tail entries up to `Qw/Qa`; 5) set `state = CLOSED` with the recovered `lastEntryId`/`length`. |
| **Post** | The ledger is `CLOSED` at a single, well-defined `lastEntryId`. **No split-brain**: the previously-active writer cannot commit any entry beyond `lastEntryId` (its writes are fenced). All readers converge on identical contents. |
| **Errors** | `MetadataError`, `RecoveryFailed` (insufficient bookies to establish the tail). |

## Fault-tolerance contract (summary)

| Property | Condition | Tolerance |
| --- | --- | --- |
| No loss of an acked entry | journal fsync on `Qa` bookies | up to `Qa − 1` simultaneous bookie failures |
| Entry remains readable | `Qw` replicas | up to `Qw − 1` failures |
| Writer can keep appending | spare bookies for ensemble change | until the cluster cannot form a write quorum |
| One agreed history | recovery + fencing | writer crash and/or network partition |
