# Entries

An **entry** is the atomic unit of data in BookKeeper: a single record appended to a
ledger. Entries are written **sequentially** and **at most once** — once an entry id is
assigned and committed, its bytes never change.

## Fields of an entry

| Field | Meaning |
| --- | --- |
| **Ledger number** | The id of the [ledger](./ledgers.md) this entry belongs to. |
| **Entry number** | The id of this entry *within* the ledger. Entry ids are monotonically increasing and contiguous (no gaps below LAC). |
| **Last confirmed (LC)** | The id of the last entry the writer had confirmed at the time this entry was written — the writer's [LAC](./last-add-confirmed.md) value, piggybacked onto the entry. |
| **Data** | The actual payload bytes supplied by the client. BookKeeper treats this as opaque. |
| **Authentication code** | A message authentication / digest code computed over the other fields so corruption or tampering is detectable. |

```text
  ┌───────────────────────────────────────────────────────────────┐
  │ ledgerId │ entryId │ lastConfirmed │      data      │  digest   │
  └───────────────────────────────────────────────────────────────┘
```

## The piggybacked Last-Confirmed field

A subtle but important detail: every entry carries the writer's **last confirmed** value.
Because the writer only advances its LAC after `Qa` bookies acknowledge an earlier entry,
the LC embedded in entry *e* tells a reader "by the time I wrote *e*, everything up to LC
was already committed." This is how the [LAC](./last-add-confirmed.md) propagates to
readers for free as they read the stream, in addition to explicit `readLac`/long-poll
requests.

## Digest / authentication

Each entry is protected by a digest selected when the ledger is created. Common digest
types:

- **CRC32** / **CRC32C** — checksums for corruption detection (CRC32C is hardware
  accelerated and the usual choice).
- **HMAC (MAC)** — keyed authentication using the ledger password, for tamper detection.
- **DUMMY** — no digest (testing only).

The digest lets a reader verify an entry it receives from a bookie is exactly what the
writer produced — a property the [Autonomyx BookKeeping](../service-autonomyx-bookkeeping.md)
service relies on so a decision record cannot be silently altered on disk or in transit.

## Immutability

An entry is **append-only**. There is no update or delete of an individual entry; the unit
of deletion is the whole ledger. Corrections in the service layer are modeled as *new*
entries that supersede earlier ones, preserving the full audit history.
