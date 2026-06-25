# ard — make every agent discoverable

`ard` is the **build → deploy → discover** layer of the AgentWorld ecosystem.
It ships as a **box** (a [Cloud Native Buildpacks](https://buildpacks.io) builder)
you hand to a developer; at their desk it **detects their environment**, **builds**
their agent into an **OCI image**, the **pod manager** runs it as a *tool server*
or *skill server*, and every server publishes an **[A2A](https://a2a-protocol.org)
agent card** at `/.well-known/agent.json` so the **registry** can discover it.

> Dependency-free Python core + CLI (standard library only). The buildpacks are
> standard CNB and run via `pack`.

## Nodes ard bridges to

There is **no canonical org** — the ecosystem is a mesh of nodes, and some repos
are shared across them. ard is one node; it federates and bridges with others:

| Node | Domain | ard bridge |
| --- | --- | --- |
| **agx** (igsec) | the broad base: **identity · governance · auth · security** | governance/security events + identity/auth |
| `Agent-MCPs` | registry of MCP/agent servers | catalog / discovery federation |
| `agent-lifecycle-management` | agent identity lifecycle | card identity |
| `Agent-Sign` | Sigstore/Cosign signing (OCI/SBOM) | signs the box images |
| **ard** | build → deploy → discover | the node tying these together |

## The loop

```
ard detect ./my-agent                         # which buildpack claims it
ard build  ./my-agent --image ghcr.io/acme/agent:0.1   # CNB → OCI ("the box")
ard deploy --image ghcr.io/acme/agent:0.1 --card card.json   # run as a pod
ard serve                                      # the discovery registry
ard discover --skill refund --kind tool        # find agents by capability
```

Becoming discoverable from code is a couple of lines:

```python
from ard import discoverable

@discoverable(name="billing", kind="tool", skills=["refund", "invoice.lookup"])
class BillingAgent: ...
```

## The box (Cloud Native Buildpacks)

```bash
# build the box (your desk / CI), then build any agent with it
pack builder create ard/box --config builder.toml
pack build ghcr.io/acme/agent:0.1 --builder ard/box --path ./my-agent
```

`buildpacks/ard-python` and `buildpacks/ard-node` each `detect` their stack and,
in `build`, install deps, emit the agent's A2A card, and set the web process.
`builder.toml` assembles them into the box.

## Architecture

| Module | Responsibility |
| --- | --- |
| `ard/card.py` | A2A agent card — the universal descriptor (+ `x-ard` kind) |
| `ard/detect.py` | environment detection (the read side of build-at-desk) |
| `ard/builder.py` | drives the CNB lifecycle (`pack`) to bake the OCI image |
| `ard/pod.py` | pod manager — deploy/track tool & skill servers (local / manifest runtimes) |
| `ard/k8s.py` | render Deployment + Service for a built image |
| `ard/registry.py` · `ard/api.py` · `ard/server.py` | the discovery hub |
| `ard/sdk.py` | `@discoverable` — the per-agent adoption surface |
| `buildpacks/` · `builder.toml` | the CNB buildpacks and the box |

## Run / test

```bash
pip install -e .        # provides the `ard` CLI
pip install pytest && pytest    # 26 tests
```

## MVP scope (honest)

- **Building the OCI image** needs `pack` + a container runtime at the user's
  desk; without them `ard build` prints the exact plan (`--dry-run`).
- The pod manager ships a **local Docker runtime** and a **K8s manifest**
  runtime (emits `kubectl apply`-ready JSON); wiring a live cluster client is
  the next step.
- **AuthX-ID identity is implemented** — cards carry an identity + A2A
  `securitySchemes` and are discoverable by issuer; JWT *signature* verification
  (issuer JWKS) is the next step.
- **Bridges & tunnels** ship as tested interfaces — governance → `Platform`,
  catalog → `services`/`Skills`, SeaTunnel → lakehouse (Iceberg/Paimon) /
  Accumulo. Running them live needs the corresponding cluster. See
  [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Dependencies

ard is **dependency-free at runtime** — the core engine and CLI use only the
Python standard library, so there is nothing third-party to install, pin, or
CVE-patch to *run* it.

| Scope | Dependency | Pinned via |
| --- | --- | --- |
| Runtime (core + CLI) | none (Python ≥ 3.10 stdlib) | — |
| Dev / test | `pytest` (`>=8,<9`) | `requirements-dev.txt` (+ hashed lock at desk) |
| Build ("the box") | CNB lifecycle + base images | `builder.toml`, digest-pinned via `scripts/pin-base-images.sh` |
| Per-agent build | that agent's own deps | its `requirements.txt` / `package-lock.json` |
| Data plane (tunnels) | Apache SeaTunnel + sink (Iceberg/Paimon/Accumulo) | job version pins |

External services are **bridged, not bundled**: AuthX-ID (identity), Platform
(governance), services/Skills (catalog) and the lakehouse are reached through
the interfaces in `ard/bridges.py` and `ard/tunnels.py`.

## Reproducibility & pinning

- **Core has zero runtime deps** (stdlib) — nothing to pin or CVE-patch at runtime.
- **Dev/CI**: `requirements-dev.txt` bounds `pytest`; generate a hashed lock with
  `pip-compile --generate-hashes` / `uv lock`. CI pins `actions/*` and Python.
- **The box**: pin the CNB base images **by digest** — run
  `scripts/pin-base-images.sh` and paste the `@sha256:…` refs into `builder.toml`.
  Buildpacks are versioned; each agent pins its own deps via its lockfile.
- **Signing**: sign the box's OCI images + SBOM with `AGenNext/Agent-Sign`
  (Sigstore/Cosign); deploy only verified digests.
- **Deploys**: reference built images **by digest** (`image@sha256:…`), not
  floating tags, in the pod manager / K8s manifests; pin SeaTunnel + connectors.
