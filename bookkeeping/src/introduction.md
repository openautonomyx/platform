# Introduction

This book documents **Autonomyx BookKeeping** — a platform service that provides a
durable, strictly-ordered, append-only **ledger** for decision governance on the
Autonomyx Decision Intelligence Platform (DIP) — and the open-source **tool** that
powers it, **[Apache BookKeeper](https://bookkeeper.apache.org/)**.

It is built as an [mdBook](https://rust-lang.github.io/mdBook/) so it can be browsed,
searched, and rendered to static HTML, and it doubles as the catalog entry for the
service and the tool within the platform.

## Why a ledger belongs in a Decision Intelligence Platform

A DIP must "apply governance principles to DI by **logging, auditing** and advancing
decision making with an accountability framework for secure, safe, ethical,
transparent, repeatable, outcome-led decisions" — and it must do so while orchestrating
"the reliable, scalable and efficient batch and real-time operations of decision
services."

Those two mandatory capabilities — **decision governance** and **decision execution** —
both need the same primitive: an **immutable, totally-ordered record of what happened**.
Every decision request, model version, input snapshot, recommendation, human override,
and outcome must be written exactly once, in order, and never silently changed. That is
precisely the guarantee a write-ahead log provides, and it is exactly what Apache
BookKeeper was designed to deliver at scale.

**Autonomyx BookKeeping** packages that primitive as a first-class, reusable decision
service so other components on the platform can append and replay decision history
without each re-implementing durability, replication, and ordering.

## How to read this book

| Part | What you'll find |
| --- | --- |
| **Catalog Entries** | The platform-level definitions of the *service* (Autonomyx BookKeeping) and the *tool* (Apache BookKeeper). |
| **The BookKeeper Protocol** | A from-first-principles walkthrough of entries, ledgers, bookies, ensembles, quorums, LAC, recovery, fencing, and the guarantees they compose into. |
| **Contracts** | Formal interface contracts — operation signatures with pre/post-conditions and invariants — for both the service and the underlying protocol. |
| **Appendix** | Glossary and references. |

## Building this book

```bash
# from the repository root
cd bookkeeping
mdbook build      # renders static HTML into bookkeeping/book/
mdbook serve      # live-preview at http://localhost:3000
```

> The protocol descriptions in this book follow the official
> [Apache BookKeeper protocol documentation](https://bookkeeper.apache.org/docs/development/protocol).
