# ard in the AgentWorld (openagx) ecosystem

ard is the **build → deploy → discover** layer, with **bridges** to the rest of
the ecosystem and **tunnels** to the data plane.

```
            ┌─────────────────────── ard ───────────────────────┐
  detect →  │  buildpacks (the box, CNB) → OCI image             │
            │  pod manager → tool/skill server pods              │
  publish → │  A2A agent card  +  AuthX-ID identity              │
            │  registry + discovery API  ── discover.agennext.com│
            └───┬──────────────┬───────────────┬────────────────┘
         bridges│              │catalog        │governance
                ▼              ▼               ▼
          AuthX-ID       services / Skills   Platform
         (identity)        (catalog)       (governance)
                                │ tunnels (SeaTunnel)
                                ▼
                    lakehouse (Iceberg/Paimon) · Accumulo (secure)
```

## Ecosystem map

| openagx repo | Role | ard connection | Status |
| --- | --- | --- | --- |
| `AuthX-ID` | agent **identity** | cards carry `identity` + `securitySchemes`; discover by issuer | ✅ built + tested (`ard/identity.py`) |
| `Platform` | autonomous **governance** | `GovernanceSink` streams register/deploy events | ✅ interface + registry wired (`ard/bridges.py`) |
| `services` / `Skills` | **catalog** of tool/skill servers | `to_catalog_entry` routes by kind | ✅ built + tested |
| `website` / `discussion-board` | surfaces | `discover.agennext.com` consumes the registry/API | 🔌 API ready |

## Bridges (`ard/bridges.py`, `ard/identity.py`)

- **Identity → AuthX-ID.** `AuthXIdentity` + `secure_with_authx()` put an
  AuthX-ID on the card and require it via standard A2A `security`. Discovery
  filters by `issuer`. Token *signature* verification (issuer JWKS) is next.
- **Governance → Platform.** `Registry(sink=…)` emits `registered` /
  `deregistered` events to a `GovernanceSink` (`JsonlSink` ships; the Platform
  feed is a drop-in).
- **Catalog → services / Skills.** `to_catalog_entry(card)` projects a card into
  a catalog row, routed `tool → openagx/services`, `skill → openagx/Skills`.

## Tunnels (`ard/tunnels.py`)

A *tunnel* is an **Apache SeaTunnel** job that streams the discovery/governance
feed into the data plane:

- **Lakehouse** — `seatunnel_job(..., sink="iceberg"|"paimon")` → Apache
  Iceberg / Paimon table.
- **Secure store** — `sink="accumulo"` → Apache Accumulo (cell-level security
  that pairs with AuthX-ID identities).

ard *generates* the job spec (`to_hocon`); SeaTunnel *executes* it on a cluster.

## Evidence

- **39 tests pass** (`pytest`): card · detect · k8s · pod · registry/api ·
  builder · CNB artifacts · sdk · **identity** · **bridges** · **tunnels**.
- Dependency-free Python core + CLI; CNB buildpacks under `buildpacks/`.

Legend: ✅ built + tested · 🔌 interface ready, live wiring needs the
corresponding cluster/service.
