# ard — a node in the AgentWorld mesh

ard is the **build → deploy → discover** layer, with **bridges** to peer nodes
and **tunnels** to the data plane. There is **no canonical org** — peers
federate, and **each publishes its own format**:

| Node | Analogy | Domain | Publishes |
| --- | --- | --- | --- |
| **autonomyx** | Gartner | Decision-Intelligence & governance **frameworks** | DIP / BOAT framing, decision & governance formats |
| **AGenNext** | Anthropic | the **agent** ecosystem (agents, MCPs, ard) | agent formats — A2A cards, AgentQL |
| **agx** | Okta | **identity · auth · security · governance** | identity / auth & signing formats |

ard speaks all three: it builds & makes agents discoverable (AGenNext), carries
identity/auth (agx), and emits governance events (autonomyx). Some repos are
shared across nodes; everything federates.

```
            ┌─────────────────────── ard ───────────────────────┐
  detect →  │  buildpacks (the box, CNB) → OCI image             │
            │  pod manager → tool/skill server pods              │
  publish → │  A2A agent card  +  identity                       │
            │  registry + discovery API  ── discover.agennext.com│
            └───┬──────────────┬───────────────┬────────────────┘
         bridges│              │catalog        │governance
                ▼              ▼               ▼
   agent-lifecycle-     Agent-MCPs        agx (igsec platform)
   management (identity)  (registry)      governance + security
                                │ tunnels (SeaTunnel)
                                ▼
                    lakehouse (Iceberg/Paimon) · Accumulo (secure)
```

## Node map (no canonical org — a mesh; some repos are shared)

**Every repo is a node** that publishes its own format/descriptor; ard federates
node-to-node, regardless of which org owns the repo.

| Repo node | Role | ard connection | Status |
| --- | --- | --- | --- |
| `agent-lifecycle-management` | agent **identity** lifecycle | cards carry `identity` + `securitySchemes`; discover by issuer | ✅ model built + tested (`ard/identity.py`) |
| `Agent-MCPs` | **registry** of MCP/agent servers | `to_catalog_entry` projects cards into registry entries | ✅ built + tested (`ard/bridges.py`) |
| `Agent-Sign` | Sigstore/Cosign **signing** (OCI/SBOM/provenance) | sign the box images; deploy verified digests | 🔌 documented (pinning + `scripts/pin-base-images.sh`) |
| _agx_ (igsec platform) | security + autonomous **governance** | `GovernanceSink` streams register/deploy events | ✅ interface + registry wired |
| `discover.agennext.com` | discovery **surface** | consumes the registry/API | 🔌 API ready |

## Bridges (`ard/bridges.py`, `ard/identity.py`)

- **Identity → agent-lifecycle-management.** `AuthXIdentity` + `secure_with_authx()`
  put an identity on the card and require it via standard A2A `security`;
  discovery filters by `issuer`. Token *signature* verification (issuer JWKS) is next.
- **Catalog → Agent-MCPs.** `to_catalog_entry(card)` projects a card into a
  registry entry for the AGenNext agent/MCP registry, tagged by `kind`.
- **Governance/security → agx (igsec platform).** `Registry(sink=…)` emits
  `registered` / `deregistered` events to a `GovernanceSink` (`JsonlSink` ships;
  the agx security/governance feed is a drop-in).
- **Signing → Agent-Sign.** The box's OCI images + SBOM are signed with
  Sigstore/Cosign; deploys reference verified digests (see Reproducibility in
  the README).

## Tunnels (`ard/tunnels.py`)

An **Apache SeaTunnel** job streams the discovery/governance feed into the data plane:

- **Lakehouse** — `seatunnel_job(..., sink="iceberg"|"paimon")` → Apache Iceberg / Paimon.
- **Secure store** — `sink="accumulo"` → Apache Accumulo (cell-level security
  that pairs with agent identities).

ard *generates* the job spec (`to_hocon`); SeaTunnel *executes* it.

## Evidence

- **39 tests pass** (`pytest`): card · detect · k8s · pod · registry/api ·
  builder · CNB artifacts · sdk · identity · bridges · tunnels.
- Dependency-free Python core + CLI; CNB buildpacks under `buildpacks/`.

Legend: ✅ built + tested · 🔌 interface ready, live wiring needs the
corresponding cluster/service.

> **No canonical org.** The ecosystem is a node mesh: **agx** is the broad base
> (identity · governance · auth · security), AGenNext holds agent nodes
> (Agent-MCPs, lifecycle, signing), and some repos are shared. ard is a node that
> bridges/federates with them. The live Console sits on `openautonomyx/platform`
> only because that's this session's write scope; it relocates wherever you point
> me once that repo is in scope.
