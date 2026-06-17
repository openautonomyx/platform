# Autonomyx BookKeeping — mdBook

This directory is an [mdBook](https://rust-lang.github.io/mdBook/) documenting:

- **Autonomyx BookKeeping** — a platform *service*: a durable, ordered, append-only ledger
  for decision governance & execution on the Autonomyx Decision Intelligence Platform.
- **Apache BookKeeper** — the open-source *tool* that powers it, including a from-first-
  principles walkthrough of its protocol and a formal set of contracts.

## Layout

```text
bookkeeping/
├── book.toml                 # mdBook configuration
└── src/
    ├── SUMMARY.md            # table of contents
    ├── introduction.md
    ├── service-autonomyx-bookkeeping.md   # the SERVICE catalog entry
    ├── tool-apache-bookkeeper.md          # the TOOL catalog entry
    ├── protocol/             # the BookKeeper protocol, chapter by chapter
    ├── contracts/            # service + protocol interface contracts
    ├── glossary.md
    └── references.md
```

## Build ("bind") the book

```bash
cd bookkeeping
mdbook build      # renders static HTML into ./book/
mdbook serve      # live preview at http://localhost:3000
```

`mdbook` install (if needed): a prebuilt binary from the
[mdBook releases](https://github.com/rust-lang/mdBook/releases), or `cargo install mdbook`.

The rendered output (`book/`) is generated and is **not** committed (see `.gitignore`);
build it locally or in CI / GitHub Pages.

Protocol content follows the official
[Apache BookKeeper protocol docs](https://bookkeeper.apache.org/docs/development/protocol).
